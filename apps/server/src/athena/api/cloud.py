"""Cloud storage through rclone: remotes, browsing a remote like a location, and copy,
move and sync jobs between locations and remotes (docs/mvp-design.md §4.4).

Everything needs the `cloud.rclone` capability. Only admins add, change or remove
remotes. A remote's paths are checked by athena.cloud.remotes (no `..`), and a
location's by athena.files.paths, before rclone sees them.
"""

import asyncio
import contextlib
import shutil
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from athena import audit
from athena.api.files import (
    INLINE_TYPES,
    SAFE_HEADERS,
    UPLOAD_ID,
    DeleteOut,
    ItemError,
    Paths,
    UploadOut,
    _disposition,
    _location,
    receive_chunk,
)
from athena.auth.deps import Authed, DbSession
from athena.cloud import remotes, transfers
from athena.cloud.rclone import Download, Rclone, RcloneError
from athena.cloud.remotes import (
    ConfigStep,
    Provider,
    RemoteDetail,
    RemoteOut,
    check_path,
    fs_of,
    join,
)
from athena.cloud.transfers import Step, SyncPreview
from athena.files.ops import FileEntry, Listing
from athena.files.paths import BadPath, Conflict, FileError, check_new_name, existing_entry, resolve
from athena.jobs import JobManager, JobOut
from athena.platform.store import CapabilityStore

CAPABILITY = "cloud.rclone"
STALE_UPLOAD_SECONDS = 24 * 3600


async def require_rclone(request: Request) -> None:
    store: CapabilityStore = request.app.state.capabilities
    cap = (await store.get()).get(CAPABILITY)
    if cap is None or cap.status != "ready":
        detail = cap.detail if cap and cap.detail else "rclone isn't installed on this host"
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail)


router = APIRouter(prefix="/cloud", tags=["cloud"], dependencies=[Depends(require_rclone)])

RemoteName = Annotated[str, Query(min_length=1, max_length=64)]
RelPath = Annotated[str, Query(max_length=4096)]


class RemoteIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    type: Annotated[str, Field(min_length=1, max_length=64)]
    parameters: dict[str, Annotated[str, Field(max_length=65536)]] = {}


class RemoteUpdateIn(BaseModel):
    parameters: dict[str, Annotated[str, Field(max_length=65536)]] = {}
    """Secrets sent empty keep their value."""


class AnswerIn(BaseModel):
    state: Annotated[str, Field(min_length=1, max_length=4096)]
    answer: Annotated[str, Field(max_length=65536)]


class CloudFolderIn(BaseModel):
    remote: str
    path: Annotated[str, Field(max_length=4096)] = ""
    name: str


class CloudRenameIn(BaseModel):
    remote: str
    path: Annotated[str, Field(min_length=1, max_length=4096)]
    name: str


class CloudDeleteIn(BaseModel):
    remote: str
    paths: Paths
    """Deleted for good: remotes have no trash Athena can use (some keep their own)."""


class Place(BaseModel):
    """A folder in a location or on a remote: exactly one of `location` and `remote`."""

    location: int | None = None
    remote: str | None = None
    path: Annotated[str, Field(max_length=4096)] = ""

    @model_validator(mode="after")
    def _one(self) -> "Place":
        if (self.location is None) == (self.remote is None):
            raise ValueError("Give either a location or a remote")
        return self


class CloudTransferIn(BaseModel):
    op: Literal["copy", "move"]
    source: Place
    """Where `paths` are relative to (the location's or remote's root)."""
    paths: Paths
    dest: Place
    """The folder to put them in. A file that's already there is replaced if it differs."""


class SyncIn(BaseModel):
    source: Place
    dest: Place


def rclone_of(request: Request) -> Rclone:
    return request.app.state.rclone


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, FileError):
        return HTTPException(exc.status, exc.message)
    if isinstance(exc, RcloneError):
        code = exc.status if exc.status in (400, 403, 404, 409, 503, 504) else 502
        return HTTPException(code, exc.message)
    raise exc


async def _do[T](work: Awaitable[T]) -> T:
    try:
        return await work
    except (FileError, RcloneError) as exc:
        raise _fail(exc) from exc


def _admin(user: Authed) -> None:
    if not user.user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can change remotes")


# --- Remotes ---------------------------------------------------------------------------


@router.get("/providers", operation_id="listCloudProviders")
async def list_providers(request: Request) -> list[Provider]:
    return await _do(remotes.providers(rclone_of(request)))


@router.get("/remotes", operation_id="listCloudRemotes")
async def list_remotes(request: Request) -> list[RemoteOut]:
    return await _do(remotes.remotes(rclone_of(request)))


@router.get("/remotes/{name}", operation_id="getCloudRemote")
async def get_remote(name: str, request: Request, user: Authed) -> RemoteDetail:
    _admin(user)
    return await _do(remotes.remote(rclone_of(request), name))


@router.post("/remotes", operation_id="createCloudRemote", status_code=status.HTTP_201_CREATED)
async def create_remote(
    body: RemoteIn, request: Request, user: Authed, db: DbSession
) -> ConfigStep:
    """Creates the remote, then returns rclone's first follow-up question, if any."""
    _admin(user)
    step = await _do(remotes.create(rclone_of(request), body.name, body.type, body.parameters))
    audit.record(db, user.user.username, "cloud.remote.create", body.name, body.type)
    return step


@router.put("/remotes/{name}", operation_id="updateCloudRemote")
async def update_remote(
    name: str, body: RemoteUpdateIn, request: Request, user: Authed, db: DbSession
) -> ConfigStep:
    _admin(user)
    step = await _do(remotes.update(rclone_of(request), name, body.parameters))
    audit.record(db, user.user.username, "cloud.remote.edit", name)
    return step


@router.post("/remotes/{name}/answer", operation_id="answerCloudRemote")
async def answer_remote(name: str, body: AnswerIn, request: Request, user: Authed) -> ConfigStep:
    """Answer the question a create or update returned."""
    _admin(user)
    return await _do(remotes.answer(rclone_of(request), name, body.state, body.answer))


@router.delete(
    "/remotes/{name}", operation_id="deleteCloudRemote", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_remote(name: str, request: Request, user: Authed, db: DbSession) -> Response:
    """Athena forgets the remote; nothing stored on it is touched."""
    _admin(user)
    await _do(remotes.delete(rclone_of(request), name))
    audit.record(db, user.user.username, "cloud.remote.remove", name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Browsing --------------------------------------------------------------------------


async def _known(rclone: Rclone, name: str) -> None:
    if not await remotes.exists(rclone, name):
        raise remotes.NotFound(f"There's no remote called {name}")


@router.get("/files/list", operation_id="listCloudFiles")
async def list_files(request: Request, remote: RemoteName, path: RelPath = "") -> Listing:
    return await _do(remotes.list_dir(rclone_of(request), remote, path))


@router.get(
    "/files/download",
    operation_id="downloadCloudFile",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download(
    request: Request, remote: RemoteName, path: RelPath, inline: bool = False
) -> Response:
    """A file from the remote, streamed. Folders can't be downloaded: copy them to a
    location first. Like the file manager, only images, audio and video show inline."""
    rclone = rclone_of(request)

    async def open_() -> tuple[FileEntry, Download]:
        await _known(rclone, remote)
        entry = await remotes.stat(rclone, remote, path)
        if entry is None:
            raise remotes.NotFound("That file doesn't exist")
        if entry.kind != "file":
            raise BadPath("Folders on a remote can't be downloaded; copy them to a location")
        return entry, await rclone.download(fs_of(remote), check_path(path))

    entry, stream = await _do(open_())
    media = INLINE_TYPES.get(Path(entry.name).suffix.lower())
    show = inline and media is not None
    headers = {
        "Content-Disposition": _disposition("inline" if show else "attachment", entry.name),
        **SAFE_HEADERS,
    }
    if stream.size is not None:
        headers["Content-Length"] = str(stream.size)
    return StreamingResponse(
        stream.chunks,
        media_type=media if show else "application/octet-stream",
        headers=headers,
    )


# --- Changing --------------------------------------------------------------------------


@router.post("/files/folder", operation_id="createCloudFolder", status_code=status.HTTP_201_CREATED)
async def create_folder(body: CloudFolderIn, request: Request) -> FileEntry:
    rclone = rclone_of(request)

    async def work() -> FileEntry:
        await _known(rclone, body.remote)
        target = join(check_path(body.path), check_new_name(body.name))
        if await remotes.stat(rclone, body.remote, target) is not None:
            raise Conflict(f"{body.name} already exists")
        await rclone.call("operations/mkdir", {"fs": fs_of(body.remote), "remote": target})
        return FileEntry(name=body.name, path=target, kind="dir")

    return await _do(work())


@router.post("/files/rename", operation_id="renameCloudFile")
async def rename(body: CloudRenameIn, request: Request) -> FileEntry:
    rclone = rclone_of(request)

    async def work() -> FileEntry:
        await _known(rclone, body.remote)
        path = check_path(body.path)
        if not path:
            raise BadPath("The remote itself can't be renamed")
        entry = await remotes.stat(rclone, body.remote, path)
        if entry is None:
            raise remotes.NotFound("That file doesn't exist")
        parent = path.rpartition("/")[0]
        target = join(parent, check_new_name(body.name))
        if target == path:
            return entry
        # Some remotes are case-insensitive: a case-only rename finds itself here.
        if target.lower() != path.lower() and await remotes.stat(rclone, body.remote, target):
            raise Conflict(f"{body.name} already exists")
        root = fs_of(body.remote)
        if entry.kind == "dir":
            await rclone.call(
                "sync/move",
                {
                    "srcFs": fs_of(body.remote, path),
                    "dstFs": fs_of(body.remote, target),
                    "createEmptySrcDirs": True,
                    "deleteEmptySrcDirs": True,
                },
            )
            with contextlib.suppress(RcloneError):
                await rclone.call("operations/rmdir", {"fs": root, "remote": path})
        else:
            await rclone.call(
                "operations/movefile",
                {"srcFs": root, "srcRemote": path, "dstFs": root, "dstRemote": target},
            )
        return entry.model_copy(update={"name": body.name, "path": target})

    return await _do(work())


@router.post("/files/delete", operation_id="deleteCloudFiles")
async def delete(body: CloudDeleteIn, request: Request, user: Authed, db: DbSession) -> DeleteOut:
    rclone = rclone_of(request)
    await _do(_known(rclone, body.remote))
    root = fs_of(body.remote)
    deleted: list[str] = []
    errors: list[ItemError] = []
    for rel in body.paths:
        try:
            path = check_path(rel)
            if not path:
                raise BadPath("The remote itself can't be deleted")
            entry = await remotes.stat(rclone, body.remote, path)
            if entry is None:
                raise remotes.NotFound("It doesn't exist")
            method = "operations/purge" if entry.kind == "dir" else "operations/deletefile"
            await rclone.call(method, {"fs": root, "remote": path})
            deleted.append(rel)
        except (FileError, RcloneError) as exc:
            errors.append(ItemError(path=rel, error=_fail(exc).detail))
    if deleted:
        more = f" and {len(deleted) - 20} more" if len(deleted) > 20 else ""
        audit.record(
            db,
            user.user.username,
            "cloud.delete",
            f"{body.remote}:",
            ", ".join(deleted[:20]) + more,
        )
    return DeleteOut(deleted=deleted, errors=errors)


# --- Uploads ---------------------------------------------------------------------------


def _staging(rclone: Rclone, upload_id: str) -> Path:
    return rclone.dir / "uploads" / upload_id


def _clear_stale(rclone: Rclone) -> None:
    folder = rclone.dir / "uploads"
    if not folder.is_dir():
        return
    cutoff = time.time() - STALE_UPLOAD_SECONDS
    for item in folder.iterdir():
        with contextlib.suppress(OSError):
            if item.stat().st_mtime < cutoff:
                shutil.rmtree(item, ignore_errors=True)


@router.post(
    "/files/upload",
    operation_id="uploadCloudChunk",
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
    remote: RemoteName,
    name: Annotated[str, Query(min_length=1, max_length=255)],
    upload_id: Annotated[str, Query(pattern=UPLOAD_ID.pattern)],
    offset: Annotated[int, Query(ge=0)],
    total: Annotated[int, Query(ge=0)],
    path: RelPath = "",
    overwrite: bool = False,
) -> UploadOut:
    """Like /api/files/upload: pieces in order. They're kept on the server, and the file
    is sent to the remote after the last one, so that request takes longer."""
    rclone = rclone_of(request)
    try:
        folder = check_path(path)
    except FileError as exc:
        raise _fail(exc) from exc
    staging = _staging(rclone, upload_id)

    async def prepare() -> None:
        await _known(rclone, remote)
        target = join(folder, check_new_name(name))
        if offset == 0:
            await asyncio.to_thread(_clear_stale, rclone)
            if not overwrite and await remotes.stat(rclone, remote, target) is not None:
                raise Conflict(f"{name} already exists")
        staging.mkdir(parents=True, exist_ok=True)

    await _do(prepare())
    got = await receive_chunk(
        request, staging, staging, name, upload_id, offset, total, "overwrite"
    )
    if got.entry is None:
        return got

    async def send() -> FileEntry:
        target = join(folder, name)
        try:
            await rclone.call(
                "operations/movefile",
                {
                    "srcFs": str(staging),
                    "srcRemote": name,
                    "dstFs": fs_of(remote),
                    "dstRemote": target,
                },
            )
        finally:
            await asyncio.to_thread(shutil.rmtree, staging, True)
        entry = await remotes.stat(rclone, remote, target)
        return entry or FileEntry(name=name, path=target, kind="file", size=total)

    return UploadOut(received=got.received, entry=await _do(send()))


@router.delete(
    "/files/upload", operation_id="cancelCloudUpload", status_code=status.HTTP_204_NO_CONTENT
)
async def cancel_upload(
    request: Request, upload_id: Annotated[str, Query(pattern=UPLOAD_ID.pattern)]
) -> Response:
    await asyncio.to_thread(shutil.rmtree, _staging(rclone_of(request), upload_id), True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Transfers -------------------------------------------------------------------------


class _Resolved(BaseModel):
    fs: str
    """The rclone fs string for the folder."""
    label: str
    location: int | None = None
    remote: str | None = None
    path: str = ""
    local: str | None = None
    """The host folder, for a location."""


async def _place(request: Request, db: DbSession, place: Place) -> _Resolved:
    if place.location is not None:
        loc, root = _location(db, place.location)
        folder = await asyncio.to_thread(lambda: resolve(root, place.path))
        if not folder.is_dir():
            raise BadPath(f"{loc.name}:/{place.path.strip('/')} isn't a folder")
        path = place.path.strip("/")
        return _Resolved(
            fs=str(folder),
            label=f"{loc.name}:/{path}",
            location=place.location,
            path=path,
            local=str(folder),
        )
    assert place.remote is not None
    rclone = rclone_of(request)
    await _known(rclone, place.remote)
    path = check_path(place.path)
    return _Resolved(
        fs=fs_of(place.remote, path),
        label=f"{place.remote}:/{path}",
        remote=place.remote,
        path=path,
    )


def _inside(a: _Resolved, b: _Resolved) -> bool:
    """`b` is `a` or inside it (same location or remote)."""
    if a.local is not None and b.local is not None:
        pa, pb = Path(a.local), Path(b.local)
        return pb == pa or pa in pb.parents
    if a.remote is not None and a.remote == b.remote:
        return a.path == "" or b.path == a.path or b.path.startswith(f"{a.path}/")
    return False


@dataclass
class _Item:
    name: str
    is_dir: bool
    fs: str
    """The item itself as an rclone fs (for folders)."""
    parent: str
    """Its folder as an rclone fs (for files)."""


async def _item(request: Request, db: DbSession, place: Place, rel: str) -> _Item:
    """Item `rel`, relative to the place's root, as rclone names it."""
    if place.location is not None:
        _, root = _location(db, place.location)
        entry = await asyncio.to_thread(lambda: existing_entry(root, rel))
        return _Item(entry.name, entry.is_dir(), str(entry), str(entry.parent))
    assert place.remote is not None
    path = check_path(rel)
    if not path:
        raise BadPath("Pick items inside the remote")
    found = await remotes.stat(rclone_of(request), place.remote, path)
    if found is None:
        raise remotes.NotFound(f"{rel} doesn't exist")
    parent = path.rpartition("/")[0]
    return _Item(
        found.name,
        found.kind == "dir",
        fs_of(place.remote, path),
        fs_of(place.remote, parent),
    )


def _child(dest: _Resolved, name: str) -> str:
    if dest.local is not None:
        return str(Path(dest.local) / name)
    assert dest.remote is not None
    return fs_of(dest.remote, join(dest.path, name))


@router.post("/transfer", operation_id="transferCloudFiles", status_code=status.HTTP_202_ACCEPTED)
async def transfer(body: CloudTransferIn, request: Request, user: Authed, db: DbSession) -> JobOut:
    """Copy or move items between a location and a remote, or between remotes, as a
    job that reports progress and can be cancelled. Location to location copies use
    /api/files/transfer."""

    async def plan() -> tuple[_Resolved, list[Step]]:
        if body.source.remote is None and body.dest.remote is None:
            raise BadPath("Use the file manager's copy between locations")
        dest = await _place(request, db, body.dest)
        steps = []
        for rel in body.paths:
            item = await _item(request, db, body.source, rel)
            name = check_new_name(item.name)
            if item.is_dir:
                src = await _place(request, db, body.source.model_copy(update={"path": rel}))
                if _inside(src, dest):
                    raise BadPath(f"{name} can't go into itself")
                steps.append(
                    Step(
                        label=f"{name} → {dest.label}",
                        method="sync/copy" if body.op == "copy" else "sync/move",
                        params={
                            "srcFs": item.fs,
                            "dstFs": _child(dest, name),
                            "createEmptySrcDirs": True,
                            **({"deleteEmptySrcDirs": True} if body.op == "move" else {}),
                        },
                    )
                )
            else:
                steps.append(
                    Step(
                        label=f"{name} → {dest.label}",
                        method="operations/copyfile"
                        if body.op == "copy"
                        else "operations/movefile",
                        params={
                            "srcFs": item.parent,
                            "srcRemote": name,
                            "dstFs": dest.fs,
                            "dstRemote": name,
                        },
                    )
                )
        return dest, steps

    dest, steps = await _do(plan())
    rclone = rclone_of(request)
    verb = "Copy" if body.op == "copy" else "Move"
    count = f"{len(steps)} items" if len(steps) > 1 else body.paths[0].rsplit("/", 1)[-1]
    root = await _do(_place(request, db, body.source.model_copy(update={"path": ""})))
    source = root.label.removesuffix("/")
    audit.record(
        db,
        user.user.username,
        f"cloud.{body.op}",
        dest.label,
        f"from {source}: {', '.join(body.paths[:20])}",
    )
    jobs: JobManager = request.app.state.jobs
    return jobs.start(
        f"{verb} {count} to {dest.label}",
        lambda job: transfers.run(job, rclone, steps),
        cancellable=True,
    ).out()


async def _sync_places(
    request: Request, db: DbSession, body: SyncIn
) -> tuple[_Resolved, _Resolved]:
    src = await _place(request, db, body.source)
    dest = await _place(request, db, body.dest)
    if _inside(src, dest) or _inside(dest, src):
        raise BadPath("The folders can't be the same or inside each other")
    return src, dest


@router.post("/sync/preview", operation_id="previewCloudSync")
async def preview_sync(body: SyncIn, request: Request, db: DbSession) -> SyncPreview:
    """What a sync would do: how many files it copies, and which ones it deletes."""

    async def work() -> SyncPreview:
        src, dest = await _sync_places(request, db, body)
        return await transfers.preview_sync(rclone_of(request), src.fs, dest.fs)

    return await _do(work())


@router.post("/sync", operation_id="syncCloudFolders", status_code=status.HTTP_202_ACCEPTED)
async def sync(body: SyncIn, request: Request, user: Authed, db: DbSession) -> JobOut:
    """Make `dest` match `source`: copies new and changed files and **deletes** files
    that aren't at the source. Run the preview first."""
    src, dest = await _do(_sync_places(request, db, body))
    rclone = rclone_of(request)
    step = Step(
        label=f"Sync {src.label} → {dest.label}",
        method="sync/sync",
        params={"srcFs": src.fs, "dstFs": dest.fs, "createEmptySrcDirs": True},
    )
    audit.record(db, user.user.username, "cloud.sync", dest.label, f"from {src.label}")
    jobs: JobManager = request.app.state.jobs
    return jobs.start(
        f"Sync {src.label} to {dest.label}",
        lambda job: transfers.run(job, rclone, [step]),
        cancellable=True,
    ).out()
