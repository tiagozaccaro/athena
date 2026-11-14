"""File manager: locations, listing, text editing, downloads, chunked uploads, and
folder, rename, delete, copy and move operations (docs/mvp-design.md §4.3).

Every path is a location id plus a `/`-separated path inside it; athena.files.paths
keeps it there. Only admins add, change or remove locations.
"""

import asyncio
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from athena import audit
from athena.auth.deps import Authed, DbSession
from athena.db.models import FileLocation
from athena.files import locations, ops
from athena.files.ops import FileEntry, Listing, OnConflict, TextFile
from athena.files.paths import (
    BadPath,
    Conflict,
    FileError,
    check_new_name,
    existing_entry,
    resolve,
    root_of,
)
from athena.jobs import Job, JobManager, JobOut

router = APIRouter(prefix="/files", tags=["files"])

LocationId = Annotated[int, Query(ge=1)]
RelPath = Annotated[str, Query(max_length=4096)]
UPLOAD_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
MAX_CHUNK = 64 * 1024 * 1024
# Shown in the browser instead of downloaded. No HTML, SVG or PDF: those can run script.
INLINE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
}
# Downloads are host files, so the browser must never run them as part of the app.
SAFE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; img-src 'self'; media-src 'self'; sandbox",
}


Paths = Annotated[
    list[Annotated[str, Field(min_length=1, max_length=4096)]], Field(min_length=1, max_length=1000)
]


class LocationOut(BaseModel):
    id: int
    name: str
    path: str
    available: bool
    """The folder exists."""
    writable: bool


class LocationIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    path: Annotated[str, Field(min_length=1, max_length=1024)]


class TextIn(BaseModel):
    location: int
    path: Annotated[str, Field(min_length=1, max_length=4096)]
    content: Annotated[str, Field(max_length=ops.MAX_TEXT)]
    version: str | None = None
    """From the read; the save fails if the file changed since."""


class NewFolderIn(BaseModel):
    location: int
    path: Annotated[str, Field(max_length=4096)] = ""
    """The folder to create it in."""
    name: str


class RenameIn(BaseModel):
    location: int
    path: Annotated[str, Field(min_length=1, max_length=4096)]
    name: str


class DeleteIn(BaseModel):
    location: int
    paths: Paths
    permanent: bool = False
    """Delete instead of moving to the trash."""


class ItemError(BaseModel):
    path: str
    error: str


class DeleteOut(BaseModel):
    deleted: list[str]
    errors: list[ItemError]


class TransferIn(BaseModel):
    op: Literal["copy", "move"]
    location: int
    paths: Paths
    dest_location: int
    dest_path: Annotated[str, Field(max_length=4096)] = ""
    on_conflict: OnConflict = "rename"
    """When the name is taken: add " (1)", skip the item, or replace a file."""


class UploadOut(BaseModel):
    received: int
    """Bytes stored so far; the next chunk starts here."""
    entry: FileEntry | None = None
    """The finished file, after the last chunk."""


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, FileError):
        return HTTPException(exc.status, exc.message)
    if isinstance(exc, PermissionError):
        where = f": {exc.filename}" if exc.filename else ""
        return HTTPException(status.HTTP_403_FORBIDDEN, f"No permission{where}")
    if isinstance(exc, OSError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, exc.strerror or str(exc))
    raise exc


async def _run[T](fn: Callable[[], T]) -> T:
    """Run blocking file work in a thread and turn its errors into HTTP answers."""
    try:
        return await asyncio.to_thread(fn)
    except (FileError, OSError) as exc:
        raise _fail(exc) from exc


def _location(db: DbSession, location_id: int) -> tuple[FileLocation, Path]:
    try:
        loc = locations.get(db, location_id)
        return loc, root_of(loc.path)
    except FileError as exc:
        raise _fail(exc) from exc


def _check[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except (FileError, OSError) as exc:
        raise _fail(exc) from exc


def _admin(user: Authed) -> None:
    if not user.user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can change locations")


def _location_out(loc: FileLocation) -> LocationOut:
    assert loc.id is not None
    path = Path(loc.path)
    return LocationOut(
        id=loc.id,
        name=loc.name,
        path=loc.path,
        available=path.is_dir(),
        writable=path.is_dir() and os.access(path, os.W_OK),
    )


def _target(loc: FileLocation, rel: str) -> str:
    return f"{loc.name}:/{rel.strip('/')}"


def _disposition(kind: str, name: str) -> str:
    ascii_name = name.encode("ascii", "replace").decode().replace('"', "_").replace("?", "_")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


# --- Locations -------------------------------------------------------------------------


@router.get("/locations", operation_id="listFileLocations")
def list_locations(db: DbSession) -> list[LocationOut]:
    return [_location_out(loc) for loc in locations.all_locations(db)]


@router.post("/locations", operation_id="addFileLocation", status_code=status.HTTP_201_CREATED)
def add_location(body: LocationIn, user: Authed, db: DbSession) -> LocationOut:
    _admin(user)
    loc = _check(lambda: locations.save(db, FileLocation(name="", path=""), body.name, body.path))
    audit.record(db, user.user.username, "files.location.add", loc.name, loc.path)
    return _location_out(loc)


@router.put("/locations/{location_id}", operation_id="updateFileLocation")
def update_location(location_id: int, body: LocationIn, user: Authed, db: DbSession) -> LocationOut:
    _admin(user)
    loc = _check(lambda: locations.get(db, location_id))
    loc = _check(lambda: locations.save(db, loc, body.name, body.path))
    audit.record(db, user.user.username, "files.location.edit", loc.name, loc.path)
    return _location_out(loc)


@router.delete(
    "/locations/{location_id}",
    operation_id="removeFileLocation",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_location(location_id: int, user: Authed, db: DbSession) -> Response:
    """Only Athena forgets the location; the folder and its files stay."""
    _admin(user)
    loc = _check(lambda: locations.get(db, location_id))
    db.delete(loc)
    db.commit()
    audit.record(db, user.user.username, "files.location.remove", loc.name, loc.path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Reading ---------------------------------------------------------------------------


@router.get("/list", operation_id="listFiles")
async def list_files(location: LocationId, db: DbSession, path: RelPath = "") -> Listing:
    _, root = _location(db, location)
    return await _run(lambda: ops.list_dir(root, resolve(root, path)))


@router.get("/text", operation_id="readTextFile")
async def read_text(location: LocationId, path: RelPath, db: DbSession) -> TextFile:
    _, root = _location(db, location)
    return await _run(lambda: ops.read_text(root, resolve(root, path)))


@router.get(
    "/download",
    operation_id="downloadFile",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}, "application/zip": {}}}},
)
async def download(
    location: LocationId, db: DbSession, path: RelPath = "", inline: bool = False
) -> Response:
    """A file, or a folder as a zip. With `inline`, images, audio and video are shown in
    the browser; everything else is always an attachment."""
    loc, root = _location(db, location)
    target = _check(lambda: resolve(root, path))
    if target.is_dir():
        base = target.name if target != root else loc.name
        return StreamingResponse(
            ops.zip_folder(root, target, base),
            media_type="application/zip",
            headers={
                "Content-Disposition": _disposition("attachment", f"{base}.zip"),
                **SAFE_HEADERS,
            },
        )
    if not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That file doesn't exist")
    media = INLINE_TYPES.get(target.suffix.lower())
    show = inline and media is not None
    return FileResponse(
        target,
        media_type=media if show else "application/octet-stream",
        headers={
            "Content-Disposition": _disposition("inline" if show else "attachment", target.name),
            **SAFE_HEADERS,
        },
    )


# --- Changing --------------------------------------------------------------------------


@router.put("/text", operation_id="writeTextFile")
async def write_text(body: TextIn, db: DbSession) -> TextFile:
    _, root = _location(db, body.location)
    return await _run(
        lambda: ops.write_text(root, resolve(root, body.path), body.content, body.version)
    )


@router.post("/folder", operation_id="createFolder", status_code=status.HTTP_201_CREATED)
async def create_folder(body: NewFolderIn, db: DbSession) -> FileEntry:
    _, root = _location(db, body.location)

    def work() -> FileEntry:
        name = check_new_name(body.name)
        return ops.make_dir(root, resolve(root, body.path) / name)

    return await _run(work)


@router.post("/rename", operation_id="renameFile")
async def rename(body: RenameIn, db: DbSession) -> FileEntry:
    _, root = _location(db, body.location)

    def work() -> FileEntry:
        name = check_new_name(body.name)
        return ops.rename(root, existing_entry(root, body.path), name)

    return await _run(work)


@router.post("/delete", operation_id="deleteFiles")
async def delete(body: DeleteIn, user: Authed, db: DbSession) -> DeleteOut:
    """Moves to the trash unless `permanent`. Each path succeeds or fails on its own."""
    loc, root = _location(db, body.location)
    deleted: list[str] = []
    errors: list[ItemError] = []
    for rel in body.paths:
        try:
            await asyncio.to_thread(
                lambda rel=rel: ops.delete(existing_entry(root, rel), body.permanent)
            )
            deleted.append(rel)
        except (FileError, OSError) as exc:
            errors.append(ItemError(path=rel, error=_fail(exc).detail))
    if deleted:
        how = "permanently" if body.permanent else "to trash"
        more = f" and {len(deleted) - 20} more" if len(deleted) > 20 else ""
        shown = ", ".join(deleted[:20]) + more
        audit.record(db, user.user.username, "file.delete", _target(loc, ""), f"{how}: {shown}")
    return DeleteOut(deleted=deleted, errors=errors)


@router.post("/transfer", operation_id="transferFiles", status_code=status.HTTP_202_ACCEPTED)
async def transfer(body: TransferIn, request: Request, user: Authed, db: DbSession) -> JobOut:
    """Copy or move items, possibly to another location, as a job."""
    loc, root = _location(db, body.location)
    dest_loc, dest_root = _location(db, body.dest_location)

    def check() -> tuple[list[tuple[str, Path]], Path]:
        dest = resolve(dest_root, body.dest_path)
        if not dest.is_dir():
            raise BadPath("The destination isn't a folder")
        return [(rel, existing_entry(root, rel)) for rel in body.paths], dest

    sources, dest = await _run(check)
    verb = "Copy" if body.op == "copy" else "Move"
    count = f"{len(sources)} items" if len(sources) > 1 else sources[0][1].name
    where = _target(dest_loc, body.dest_path)

    async def work(job: Job) -> None:
        failed = 0
        for rel, src in sources:
            try:
                placed = await asyncio.to_thread(ops.transfer, body.op, src, dest, body.on_conflict)
            except (FileError, OSError) as exc:
                failed += 1
                await job.log(f"{rel}: {_fail(exc).detail}")
                continue
            if placed is None:
                await job.log(f"{rel}: skipped, {src.name} is already there")
            else:
                await job.log(f"{rel} → {placed.name}")
        if failed:
            raise RuntimeError(f"{failed} of {len(sources)} items failed")

    if body.op == "move":
        audit.record(
            db,
            user.user.username,
            "file.move",
            _target(loc, ""),
            f"{', '.join(r for r, _ in sources[:20])} → {where}",
        )
    jobs: JobManager = request.app.state.jobs
    return jobs.start(f"{verb} {count} to {where}", work).out()


# --- Uploads ---------------------------------------------------------------------------


@router.post(
    "/upload",
    operation_id="uploadChunk",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_chunk(
    request: Request,
    location: LocationId,
    db: DbSession,
    name: Annotated[str, Query(min_length=1, max_length=255)],
    upload_id: Annotated[str, Query(pattern=UPLOAD_ID.pattern)],
    offset: Annotated[int, Query(ge=0)],
    total: Annotated[int, Query(ge=0)],
    path: RelPath = "",
    overwrite: bool = False,
) -> UploadOut:
    """One piece of a file, sent as the raw request body. Send the pieces in order with
    their `offset`; the file appears under its name after the last one. A piece at
    offset 0 starts over."""
    _, root = _location(db, location)

    def prepare() -> tuple[Path, Path]:
        folder = resolve(root, path)
        if not folder.is_dir():
            raise BadPath("The folder to upload to doesn't exist")
        target = folder / check_new_name(name)
        part = ops.upload_part(folder, upload_id)
        if offset == 0:
            ops.clear_stale_uploads(folder)
            if target.exists(follow_symlinks=False) and not overwrite:
                raise Conflict(f"{name} already exists")
            if shutil.disk_usage(folder).free < total:
                raise FileError("There isn't enough free space for this file")
            part.unlink(missing_ok=True)
        size = part.stat().st_size if part.exists() else 0
        if size != offset:
            raise Conflict(f"Expected the piece at byte {size}")
        return part, target

    part, target = await _run(prepare)
    received = offset
    buffer = bytearray()
    try:
        with part.open("ab") as f:
            async for data in request.stream():
                received += len(data)
                if received > total or received - offset > MAX_CHUNK:
                    raise BadPath("The piece is larger than announced")
                buffer += data
                if len(buffer) >= ops.CHUNK:
                    await asyncio.to_thread(f.write, bytes(buffer))
                    buffer.clear()
            if buffer:
                await asyncio.to_thread(f.write, bytes(buffer))
    except (FileError, OSError) as exc:
        part.unlink(missing_ok=True)
        raise _fail(exc) from exc
    if received < total:
        return UploadOut(received=received)
    await _run(lambda: ops.finish_upload(part, target, overwrite))
    return UploadOut(received=received, entry=ops.describe(root, target))


@router.delete("/upload", operation_id="cancelUpload", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_upload(
    location: LocationId,
    db: DbSession,
    upload_id: Annotated[str, Query(pattern=UPLOAD_ID.pattern)],
    path: RelPath = "",
) -> Response:
    _, root = _location(db, location)
    await _run(lambda: ops.upload_part(resolve(root, path), upload_id).unlink(missing_ok=True))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
