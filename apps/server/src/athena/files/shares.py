"""Share links: a public token for one file or folder in a location (§4.3).

A link is read-only (view and download) or upload-only (a drop box nobody can list).
It may have a password and an expiry. Everything a link reaches is resolved against
the shared item itself, not the whole location, so a link to `photos/` can't reach
anything beside it, and a symlink inside it that points elsewhere is refused.

A password-protected link is unlocked with a cookie whose value is an HMAC of the
token keyed by the link's password hash. It needs no server-side state, and changing
or removing the password invalidates it.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from sqlmodel import Session, select

from athena.db.models import FileLocation, Share
from athena.files.paths import BadPath, FileError, NotFound, resolve, root_of

ShareMode = Literal["read", "upload"]
TOKEN_BYTES = 24


class Gone(FileError):
    status = 410


class Locked(FileError):
    """The link has a password and this browser hasn't unlocked it."""

    status = 403


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; they're stored as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def expired(share: Share) -> bool:
    expires = aware(share.expires_at)
    return expires is not None and expires <= datetime.now(UTC)


def cookie_name(share: Share) -> str:
    return f"athena_share_{share.id}"


def unlock_value(share: Share) -> str:
    assert share.password_hash
    return hmac.new(share.password_hash.encode(), share.token.encode(), hashlib.sha256).hexdigest()


def unlocked(share: Share, cookie: str | None) -> bool:
    if not share.password_hash:
        return True
    return cookie is not None and hmac.compare_digest(cookie, unlock_value(share))


def target_of(loc: FileLocation, rel: str) -> Path:
    """The shared file or folder on disk. Raises NotFound when it's gone."""
    path = resolve(root_of(loc.path), rel)
    if not path.exists():
        raise NotFound("The shared file or folder no longer exists")
    return path


def check_target(loc: FileLocation, rel: str, mode: ShareMode) -> Path:
    path = target_of(loc, rel)
    if not path.is_dir() and not path.is_file():
        raise BadPath("Only files and folders can be shared")
    if mode == "upload" and not path.is_dir():
        raise BadPath("Upload links need a folder")
    return path


@dataclass
class Opened:
    """A link that may be used now."""

    share: Share
    location: FileLocation
    target: Path
    """The shared file or folder (real path)."""


def find(db: Session, token: str) -> Share:
    share = db.exec(select(Share).where(Share.token == token)).first()
    if share is None:
        raise NotFound("This link doesn't exist or was removed")
    if expired(share):
        raise Gone("This link has expired")
    return share


def open_share(db: Session, token: str, cookie: str | None) -> Opened:
    """The link for `token`, checked: it exists, hasn't expired, is unlocked, and what it
    points to is still there."""
    share = find(db, token)
    if not unlocked(share, cookie):
        raise Locked("This link needs its password")
    loc = db.get(FileLocation, share.location_id)
    if loc is None:
        raise NotFound("This link doesn't exist or was removed")
    return Opened(share=share, location=loc, target=target_of(loc, share.path))
