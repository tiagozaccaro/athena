"""WebDAV at /dav/ through wsgidav (docs/mvp-design.md §4.3).

The root of the share lists the file manager's locations as folders; nothing outside
them is reachable. Paths go through athena.files.paths like the files API:

- `..`, empty and `.` segments are refused, and so is any name that normalizing
  changes (Windows drops trailing dots and spaces, so `...` would name the parent).
- The real path must stay inside the location's real path, and symlinks are neither
  listed nor followed (wsgidav's `follow_symlinks: False`).
- A location's own folder can't be deleted, moved or replaced through WebDAV.

It's off until an admin turns it on. Clients sign in with HTTP Basic, using the admin's
username and a separate WebDAV password that Athena generates, so the account password
(which also opens the terminal) is never sent on every request. Successful checks are
cached in memory for a few minutes, because argon2 is slow on purpose and clients send many
requests; failures are throttled per client like logins.

Every response gets a sandboxing CSP and `nosniff`: files are served from Athena's
origin, so an HTML file opened in a browser must never run as part of the app.
"""

import logging
import os
import secrets
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from a2wsgi import WSGIMiddleware
from pydantic import BaseModel, ValidationError
from sqlmodel import Session
from starlette.types import ASGIApp, Receive, Scope, Send
from wsgidav.dav_error import HTTP_FORBIDDEN, DAVError
from wsgidav.dav_provider import DAVCollection
from wsgidav.dc.base_dc import BaseDomainController
from wsgidav.fs_dav_provider import FileResource, FilesystemProvider, FolderResource
from wsgidav.wsgidav_app import WsgiDAVApp

from athena.auth.service import LoginThrottle, hash_password, verify_password
from athena.db import Database
from athena.db.models import SystemSetting
from athena.files import locations
from athena.files.paths import UPLOAD_PREFIX, FileError, entry, inside

log = logging.getLogger(__name__)

MOUNT = "/dav"
KEY = "webdav"
REALM = "Athena"
CACHE_SECONDS = 300
PASSWORD_BYTES = 18
HEADERS = [
    (b"content-security-policy", b"default-src 'none'; sandbox"),
    (b"x-content-type-options", b"nosniff"),
]


# --- Settings --------------------------------------------------------------------------


class WebDavConfig(BaseModel):
    enabled: bool = False
    username: str | None = None
    """Whose WebDAV password is set (the admin who generated it)."""
    password_hash: str | None = None


def load(db: Session) -> WebDavConfig:
    row = db.get(SystemSetting, KEY)
    if row is None:
        return WebDavConfig()
    try:
        return WebDavConfig.model_validate_json(row.value)
    except ValidationError:
        log.warning("ignoring invalid WebDAV settings")
        return WebDavConfig()


def save(db: Session, config: WebDavConfig) -> None:
    row = db.get(SystemSetting, KEY) or SystemSetting(key=KEY, value="")
    row.value = config.model_dump_json()
    db.add(row)
    db.commit()


def new_password(db: Session, username: str) -> str:
    """Replace the WebDAV password with a new random one and return it (shown once)."""
    password = secrets.token_urlsafe(PASSWORD_BYTES)
    config = load(db)
    config.username = username
    config.password_hash = hash_password(password)
    save(db, config)
    return password


# --- Locations as a DAV tree -----------------------------------------------------------


def _forbidden(message: str) -> DAVError:
    return DAVError(HTTP_FORBIDDEN, message)


def _is_location(path: str) -> bool:
    """`/<location>` itself, or the root."""
    return "/" not in path.strip("/")


class _Guarded:
    """Refuses copies and moves onto a location itself. wsgidav calls `handle_copy` and
    `handle_move` before anything else; when they return False it goes on with its own
    steps, which for an existing destination start by deleting it, or (copying a folder
    over a folder) deleting whatever the source doesn't have."""

    path: str

    def handle_copy(self, dest_path: str, *, depth_infinity: bool) -> bool:
        if _is_location(dest_path):
            raise _forbidden("A location's folder can't be replaced")
        return False

    def handle_move(self, dest_path: str) -> bool:
        if _is_location(self.path):
            raise _forbidden("A location's folder can't be moved")
        if _is_location(dest_path):
            raise _forbidden("A location's folder can't be replaced")
        return False


class File(_Guarded, FileResource):
    pass


class Folder(_Guarded, FolderResource):
    def get_member_names(self) -> list[str]:
        return [n for n in super().get_member_names() if not n.startswith(UPLOAD_PREFIX)]

    def get_display_name(self) -> str:
        return self.path.strip("/") if _is_location(self.path) else super().get_display_name()

    def handle_delete(self) -> bool:
        # Must refuse here: if delete() refused instead, wsgidav would fall back to
        # deleting every file and folder inside, one by one.
        if _is_location(self.path):
            raise _forbidden("A location's folder can't be deleted")
        return False

    def delete(self) -> None:
        if _is_location(self.path):
            raise _forbidden("A location's folder can't be deleted")
        super().delete()


class Root(DAVCollection):
    """The top of the share: one folder per location. Nothing can be created here."""

    def __init__(self, path: str, environ: dict) -> None:
        super().__init__(path, environ)
        self.name = REALM

    def get_display_name(self) -> str:
        return REALM

    def get_member_names(self) -> list[str]:
        return sorted(self.provider.roots(self.environ))

    def get_member(self, name: str) -> Any:
        return self.provider.get_resource_inst(f"/{name}", self.environ)

    def get_last_modified(self) -> None:
        return None

    def get_creation_date(self) -> None:
        return None


class LocationsProvider(FilesystemProvider):
    """All locations under one root. Uses wsgidav's file resources, with every path
    mapped through athena.files.paths."""

    def __init__(self, roots: Callable[[], dict[str, Path]]) -> None:
        # FilesystemProvider wants one root folder; this provider has many, so set up
        # what its methods use by hand.
        super(FilesystemProvider, self).__init__()
        self._roots = roots
        self.readonly = False
        self.fs_opts = {"follow_symlinks": False}
        self.shadow_map = {}
        self.root_folder_path = ""
        self.root_folder_path_real = ""

    def __repr__(self) -> str:
        return "Athena locations"

    def roots(self, environ: dict | None) -> dict[str, Path]:
        """Location name -> real folder, read once per request."""
        if environ is None:
            return self._roots()
        if "athena.roots" not in environ:
            environ["athena.roots"] = self._roots()
        return environ["athena.roots"]

    def _split(self, path: str, environ: dict | None) -> tuple[Path, str] | None:
        """(location folder, path inside it), or None for the root."""
        parts = path.strip("/").split("/", 1)
        if not parts[0]:
            return None
        root = self.roots(environ).get(parts[0])
        if root is None:
            raise DAVError(404 if self._reading(environ) else HTTP_FORBIDDEN)
        return root, parts[1] if len(parts) > 1 else ""

    @staticmethod
    def _reading(environ: dict | None) -> bool:
        return bool(environ) and environ.get("REQUEST_METHOD") in ("GET", "HEAD", "PROPFIND")

    def _loc_to_file_path(self, path: str, environ: dict | None = None) -> str:
        found = self._split(path, environ)
        if found is None:
            raise _forbidden("Only locations can be at the top")
        root, rel = found
        try:
            fp = entry(root, rel) if rel else root
        except FileError as exc:
            raise _forbidden(exc.message) from exc
        if not inside(root, Path(os.path.realpath(fp))):
            raise _forbidden("That path leads outside the location")
        return str(fp)

    def get_resource_inst(self, path: str, environ: dict) -> Any:
        if not path.strip("/"):
            return Root("/", environ)
        try:
            fp = self._loc_to_file_path(path, environ)
        except DAVError as exc:
            if exc.value == 404:
                return None
            raise
        if not os.path.lexists(fp):
            return None
        if os.path.islink(fp):
            raise _forbidden("Links aren't followed over WebDAV")
        if os.path.isdir(fp):
            return Folder(path, environ, fp)
        return File(path, environ, fp)


# --- Sign-in ---------------------------------------------------------------------------


class Credentials:
    """Checks WebDAV sign-ins against the stored config, with a short-lived cache.

    There is one WebDAV password, so the cache is one entry: the last sign-in that
    argon2 accepted, for that exact password hash. It lives only in memory and is
    compared in constant time; a new password changes the hash, so it applies at once.
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        self.throttle = LoginThrottle(limit=10)
        self._ok: tuple[str, str, str, float] | None = None
        """(password hash, username, password, valid until)."""
        self._lock = threading.Lock()

    def _cached(self, password_hash: str, username: str, password: str, now: float) -> bool:
        with self._lock:
            ok = self._ok
        if ok is None or ok[3] <= now or ok[0] != password_hash:
            return False
        # Both comparisons always run, so timing doesn't tell which one failed.
        same_user = secrets.compare_digest(ok[1].encode(), username.encode())
        same_password = secrets.compare_digest(ok[2].encode(), password.encode())
        return same_user and same_password

    def check(self, username: str, password: str, client: str) -> bool:
        if self.throttle.retry_after(client):
            return False
        for session in self.db.session():
            config = load(session)
        if not (config.enabled and config.username and config.password_hash):
            return False
        now = time.monotonic()
        if self._cached(config.password_hash, username, password, now):
            return True
        good = secrets.compare_digest(
            username.encode(), config.username.encode()
        ) and verify_password(config.password_hash, password)
        if not good:
            self.throttle.fail(client)
            return False
        with self._lock:
            self._ok = (config.password_hash, username, password, now + CACHE_SECONDS)
        return True


class DomainController(BaseDomainController):
    def __init__(self, wsgidav_app: Any, config: dict) -> None:
        super().__init__(wsgidav_app, config)
        self.credentials: Credentials = config["athena_credentials"]

    def get_domain_realm(self, path_info: str, environ: dict | None) -> str:
        return REALM

    def require_authentication(self, realm: str, environ: dict | None) -> bool:
        return True

    def basic_auth_user(self, realm: str, user_name: str, password: str, environ: dict) -> bool:
        return self.credentials.check(user_name, password, environ.get("REMOTE_ADDR", "unknown"))

    def supports_http_digest_auth(self) -> bool:
        return False


# --- The app ---------------------------------------------------------------------------


def _roots(db: Database) -> Callable[[], dict[str, Path]]:
    def roots() -> dict[str, Path]:
        found: dict[str, Path] = {}
        for session in db.session():
            for loc in locations.all_locations(session):
                path = Path(loc.path).resolve()
                if "/" not in loc.name and path.is_dir():
                    found[loc.name] = path
        return found

    return roots


def dav_app(db: Database) -> WsgiDAVApp:
    # It warns on every start about middleware that's off on purpose and about Basic
    # sign-in without TLS (the settings page says so instead).
    logging.getLogger("wsgidav").setLevel(logging.ERROR)
    return WsgiDAVApp(
        {
            "mount_path": MOUNT,
            "provider_mapping": {"/": LocationsProvider(_roots(db))},
            "http_authenticator": {
                "domain_controller": DomainController,
                "accept_basic": True,
                "accept_digest": False,
                "default_to_digest": False,
            },
            "athena_credentials": Credentials(db),
            "dir_browser": {"enable": False},
            "property_manager": True,
            "lock_storage": True,
            "hotfixes": {"emulate_win32_lastmod": True},
            "suppress_version_info": True,
            "verbose": 1,
            "logging": {"enable": False},
        }
    )


class WebDavMiddleware:
    """Sends /dav and /dav/… to wsgidav when WebDAV is on (404 otherwise), and adds the
    sandboxing headers to its answers. Everything else goes to the app."""

    def __init__(self, app: ASGIApp, db: Database) -> None:
        self.app = app
        self.db = db
        self.dav = WSGIMiddleware(dav_app(db), workers=8)  # type: ignore[arg-type]

    def _enabled(self) -> bool:
        for session in self.db.session():
            return load(session).enabled
        return False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path == MOUNT or path.startswith(MOUNT + "/")):
            await self.app(scope, receive, send)
            return
        if not self._enabled():
            await send({"type": "http.response.start", "status": 404, "headers": HEADERS})
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                skip = {name for name, _ in HEADERS}
                headers = [h for h in message.get("headers", []) if h[0].lower() not in skip]
                message = {**message, "headers": headers + HEADERS}
            await send(message)

        await self.dav({**scope, "root_path": MOUNT}, receive, send_with_headers)
