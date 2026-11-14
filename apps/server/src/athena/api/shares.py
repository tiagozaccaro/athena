"""Share links (docs/mvp-design.md §4.3).

`router` (/api/shares) is for the signed-in admin: list, create, change and remove links.

`public_router` (/api/public/shares/{token}) is what a link's visitor uses, with no
Athena account: it's the only public API besides health and /api/auth. Everything it
does is limited to the shared item (see athena.files.shares). The page that drives it
is the web UI's /s/ page, served at /s/<token> by main.py.
"""

import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from athena import audit
from athena.api.files import (
    UPLOAD_ID,
    RelPath,
    UploadOut,
    _fail,
    _location,
    _run,
    _target,
    file_response,
    receive_chunk,
)
from athena.auth.deps import Authed, DbSession
from athena.auth.service import LoginThrottle, hash_password, verify_password
from athena.db.models import FileLocation, Share
from athena.files import ops, shares
from athena.files.ops import Listing
from athena.files.paths import FileError, NotFound, resolve
from athena.files.shares import ShareMode

router = APIRouter(prefix="/shares", tags=["shares"])
public_router = APIRouter(prefix="/public/shares/{token}", tags=["public shares"])

Token = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")]
Password = Annotated[str, Field(min_length=1, max_length=256)]
UNLOCK_DAYS = 7


class ShareOut(BaseModel):
    id: int
    token: str
    url_path: str
    """Where the link opens on this server, e.g. /s/abc…; add the server's address."""
    location: int
    location_name: str
    path: str
    name: str
    """The shared file or folder's name (the location's name for the location itself)."""
    kind: ops.EntryKind | None
    """None when the shared item no longer exists."""
    mode: ShareMode
    has_password: bool
    expires_at: datetime | None
    expired: bool
    created_by: str
    created_at: datetime
    downloads: int
    uploads: int


class ShareIn(BaseModel):
    location: int
    path: Annotated[str, Field(max_length=4096)] = ""
    mode: ShareMode = "read"
    password: Password | None = None
    expires_at: datetime | None = None


class ShareUpdate(BaseModel):
    mode: ShareMode
    expires_at: datetime | None = None
    password: Password | None = None
    """A new password. Leave out to keep the current one."""
    remove_password: bool = False


def _name(loc: FileLocation, rel: str) -> str:
    rel = rel.strip("/")
    return rel.rsplit("/", 1)[-1] if rel else loc.name


def _kind(loc: FileLocation, rel: str) -> ops.EntryKind | None:
    try:
        path = shares.target_of(loc, rel)
    except (FileError, OSError):
        return None
    return "dir" if path.is_dir() else "file" if path.is_file() else "other"


def _out(share: Share, loc: FileLocation) -> ShareOut:
    assert share.id is not None and loc.id is not None
    return ShareOut(
        id=share.id,
        token=share.token,
        url_path=f"/s/{share.token}",
        location=loc.id,
        location_name=loc.name,
        path=share.path,
        name=_name(loc, share.path),
        kind=_kind(loc, share.path),
        mode=share.mode,  # type: ignore[arg-type]
        has_password=share.password_hash is not None,
        expires_at=shares.aware(share.expires_at),
        expired=shares.expired(share),
        created_by=share.created_by,
        created_at=shares.aware(share.created_at) or share.created_at,
        downloads=share.downloads,
        uploads=share.uploads,
    )


def _future(when: datetime | None) -> datetime | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    if when <= datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The expiry must be in the future")
    return when


def _share(db: Session, share_id: int) -> tuple[Share, FileLocation]:
    share = db.get(Share, share_id)
    loc = db.get(FileLocation, share.location_id) if share else None
    if share is None or loc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such link")
    return share, loc


def _describe(share: Share) -> str:
    parts = [share.mode]
    if share.password_hash:
        parts.append("password")
    if share.expires_at:
        parts.append(f"expires {shares.aware(share.expires_at):%Y-%m-%d %H:%M} UTC")
    return ", ".join(parts)


# --- Managing links --------------------------------------------------------------------


@router.get("", operation_id="listShares")
def list_shares(
    db: DbSession, location: Annotated[int | None, Query(ge=1)] = None, path: RelPath | None = None
) -> list[ShareOut]:
    """All links, newest first, or only those for one location (and path)."""
    query = select(Share, FileLocation).join(FileLocation)
    if location is not None:
        query = query.where(Share.location_id == location)
        if path is not None:
            query = query.where(Share.path == path.strip("/"))
    rows = db.exec(query.order_by(Share.id.desc())).all()  # type: ignore[union-attr]
    return [_out(share, loc) for share, loc in rows]


@router.post("", operation_id="createShare", status_code=status.HTTP_201_CREATED)
async def create_share(body: ShareIn, user: Authed, db: DbSession) -> ShareOut:
    loc, _ = _location(db, body.location)
    rel = body.path.strip("/")
    await _run(lambda: shares.check_target(loc, rel, body.mode))
    share = Share(
        token=shares.new_token(),
        location_id=body.location,
        path=rel,
        mode=body.mode,
        password_hash=hash_password(body.password) if body.password else None,
        expires_at=_future(body.expires_at),
        created_by=user.user.username,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    audit.record(db, user.user.username, "share.create", _target(loc, rel), _describe(share))
    return _out(share, loc)


@router.put("/{share_id}", operation_id="updateShare")
async def update_share(share_id: int, body: ShareUpdate, user: Authed, db: DbSession) -> ShareOut:
    """Changing or removing the password signs out everyone who unlocked the link."""
    share, loc = _share(db, share_id)
    if body.mode != share.mode:
        await _run(lambda: shares.check_target(loc, share.path, body.mode))
    share.mode = body.mode
    share.expires_at = _future(body.expires_at)
    if body.remove_password:
        share.password_hash = None
    elif body.password:
        share.password_hash = hash_password(body.password)
    db.add(share)
    db.commit()
    db.refresh(share)
    audit.record(db, user.user.username, "share.edit", _target(loc, share.path), _describe(share))
    return _out(share, loc)


@router.delete("/{share_id}", operation_id="removeShare", status_code=status.HTTP_204_NO_CONTENT)
def remove_share(share_id: int, user: Authed, db: DbSession) -> Response:
    share, loc = _share(db, share_id)
    db.delete(share)
    db.commit()
    audit.record(db, user.user.username, "share.remove", _target(loc, share.path))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Using a link (public) -------------------------------------------------------------


class PublicShare(BaseModel):
    mode: ShareMode
    locked: bool
    """The link needs its password; nothing else is told until it's unlocked."""
    name: str | None = None
    kind: ops.EntryKind | None = None
    size: int | None = None
    """Bytes, for a shared file."""
    modified: datetime | None = None
    expires_at: datetime | None = None


class UnlockIn(BaseModel):
    password: Annotated[str, Field(max_length=256)]


def _cookie(request: Request, share: Share) -> str | None:
    return request.cookies.get(shares.cookie_name(share))


def _opened(request: Request, db: Session, token: str) -> shares.Opened:
    try:
        share = shares.find(db, token)
        return shares.open_share(db, token, _cookie(request, share))
    except FileError as exc:
        raise _fail(exc) from exc


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _visitor(share: Share) -> str:
    return f"link #{share.id}"


@public_router.get("", operation_id="getPublicShare")
async def get_public_share(token: str, request: Request, db: DbSession) -> PublicShare:
    try:
        share = shares.find(db, token)
    except FileError as exc:
        raise _fail(exc) from exc
    if not shares.unlocked(share, _cookie(request, share)):
        return PublicShare(mode=share.mode, locked=True)  # type: ignore[arg-type]
    opened = _opened(request, db, token)
    entry = await _run(lambda: ops.describe(opened.target.parent, opened.target))
    return PublicShare(
        mode=share.mode,  # type: ignore[arg-type]
        locked=False,
        name=_name(opened.location, share.path),
        kind=entry.kind,
        size=entry.size,
        modified=entry.modified,
        expires_at=shares.aware(share.expires_at),
    )


@public_router.post("/unlock", operation_id="unlockPublicShare", status_code=204)
def unlock_public_share(
    token: str, body: UnlockIn, request: Request, response: Response, db: DbSession
) -> None:
    """Check the link's password and remember it in this browser for a week. A wrong
    password is 403, not 401: there's no Athena sign-in involved."""
    try:
        share = shares.find(db, token)
    except FileError as exc:
        raise _fail(exc) from exc
    if not share.password_hash:
        return
    throttle: LoginThrottle = request.app.state.share_throttle
    key = f"{_client(request)}|{share.id}"
    if wait := throttle.retry_after(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many wrong passwords. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )
    if not verify_password(share.password_hash, body.password):
        throttle.fail(key)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong password")
    throttle.reset(key)
    response.set_cookie(
        shares.cookie_name(share),
        shares.unlock_value(share),
        max_age=UNLOCK_DAYS * 24 * 3600,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path=f"/api/public/shares/{share.token}",
    )


def _readable(opened: shares.Opened) -> None:
    if opened.share.mode != "read":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This link only takes uploads")


@public_router.get("/list", operation_id="listPublicShare")
async def list_public_share(
    token: str, request: Request, db: DbSession, path: RelPath = ""
) -> Listing:
    """A folder in a shared folder; paths are relative to the shared folder."""
    opened = _opened(request, db, token)
    _readable(opened)
    root = opened.target
    if not root.is_dir():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link is for a single file")
    return await _run(lambda: ops.list_dir(root, resolve(root, path)))


@public_router.get(
    "/download",
    operation_id="downloadPublicShare",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}, "application/zip": {}}}},
)
async def download_public_share(
    token: str, request: Request, db: DbSession, path: RelPath = "", inline: bool = False
) -> Response:
    """The shared file, or a file or folder (as a zip) inside the shared folder."""
    opened = _opened(request, db, token)
    _readable(opened)
    root = opened.target
    if root.is_dir():
        target = await _run(lambda: resolve(root, path))
    elif path.strip("/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link is for a single file")
    else:
        target = root
    response = file_response(root, target, _name(opened.location, opened.share.path), inline)
    if not inline:
        opened.share.downloads += 1
        db.add(opened.share)
        db.commit()
    return response


def _upload_folder(opened: shares.Opened) -> None:
    if opened.share.mode != "upload":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This link doesn't take uploads")
    if not opened.target.is_dir():
        raise _fail(NotFound("The shared folder no longer exists"))


@public_router.post(
    "/upload",
    operation_id="uploadPublicShare",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_public_share(
    token: str,
    request: Request,
    db: DbSession,
    name: Annotated[str, Query(min_length=1, max_length=255)],
    upload_id: Annotated[str, Query(pattern=UPLOAD_ID.pattern)],
    offset: Annotated[int, Query(ge=0)],
    total: Annotated[int, Query(ge=0)],
) -> UploadOut:
    """A piece of a file for an upload link, like /api/files/upload. Files go straight
    into the shared folder and never replace anything: a taken name gets " (1)"."""
    opened = _opened(request, db, token)
    _upload_folder(opened)
    folder = opened.target
    out = await receive_chunk(request, folder, folder, name, upload_id, offset, total, "rename")
    if out.entry is not None:
        share = opened.share
        share.uploads += 1
        db.add(share)
        db.commit()
        audit.record(
            db,
            _visitor(share),
            "share.upload",
            _target(opened.location, share.path),
            f"{out.entry.name} ({out.received} bytes) from {_client(request)}",
        )
    return out


@public_router.delete(
    "/upload", operation_id="cancelPublicShareUpload", status_code=status.HTTP_204_NO_CONTENT
)
async def cancel_public_share_upload(
    token: str,
    request: Request,
    db: DbSession,
    upload_id: Annotated[str, Query(pattern=UPLOAD_ID.pattern)],
) -> Response:
    opened = _opened(request, db, token)
    _upload_folder(opened)
    await asyncio.to_thread(ops.upload_part(opened.target, upload_id).unlink, missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
