"""WebDAV settings (docs/mvp-design.md §4.3): turn the /dav/ share on or off and
generate its password. Only admins change them; see athena.files.webdav."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from athena import audit
from athena.auth.deps import Authed, DbSession
from athena.files import webdav

router = APIRouter(prefix="/webdav", tags=["webdav"])


class WebDavOut(BaseModel):
    enabled: bool
    path: str
    """Where the share is on this server; add the server's address."""
    username: str | None
    """Sign in with this username and the generated password."""
    has_password: bool


class WebDavIn(BaseModel):
    enabled: bool


class WebDavPassword(BaseModel):
    username: str
    password: str
    """Shown only now. Generating another one replaces it."""


def _admin(user: Authed) -> None:
    if not user.user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can change WebDAV")


def _out(config: webdav.WebDavConfig) -> WebDavOut:
    return WebDavOut(
        enabled=config.enabled,
        path=f"{webdav.MOUNT}/",
        username=config.username,
        has_password=config.password_hash is not None,
    )


@router.get("", operation_id="getWebDav")
def get_webdav(db: DbSession) -> WebDavOut:
    return _out(webdav.load(db))


@router.put("", operation_id="setWebDav")
def set_webdav(body: WebDavIn, user: Authed, db: DbSession) -> WebDavOut:
    _admin(user)
    config = webdav.load(db)
    if body.enabled != config.enabled:
        config.enabled = body.enabled
        webdav.save(db, config)
        audit.record(db, user.user.username, "settings.webdav", "on" if body.enabled else "off")
    return _out(config)


@router.post("/password", operation_id="newWebDavPassword")
def new_webdav_password(user: Authed, db: DbSession) -> WebDavPassword:
    """A new random password for WebDAV, replacing the old one (clients using it have to
    sign in again)."""
    _admin(user)
    password = webdav.new_password(db, user.user.username)
    audit.record(db, user.user.username, "settings.webdav", "new password")
    return WebDavPassword(username=user.user.username, password=password)
