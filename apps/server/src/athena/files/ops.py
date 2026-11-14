"""File operations inside one location. Everything here is blocking; the API runs it in
a worker thread. Paths come from athena.files.paths, so they're already inside a
location."""

import io
import logging
import os
import shutil
import stat
import time
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from send2trash import send2trash
from send2trash.exceptions import TrashPermissionError

from athena.files.paths import (
    UPLOAD_PREFIX,
    BadPath,
    Conflict,
    FileError,
    NotFound,
    available_name,
    inside,
    relative,
)

log = logging.getLogger(__name__)

MAX_ENTRIES = 10_000
MAX_TEXT = 2 * 1024 * 1024
STALE_UPLOAD_SECONDS = 24 * 3600
CHUNK = 1024 * 1024

EntryKind = Literal["dir", "file", "other"]
OnConflict = Literal["rename", "skip", "overwrite"]


class FileEntry(BaseModel):
    name: str
    path: str
    """Relative to the location, with `/` separators."""
    kind: EntryKind
    """What the entry is, after following a link."""
    size: int | None = None
    """Bytes, for files."""
    modified: datetime | None = None
    is_link: bool = False
    hidden: bool = False


class Listing(BaseModel):
    path: str
    entries: list[FileEntry]
    truncated: bool = False
    """More than MAX_ENTRIES entries; only the first ones are listed."""


class TextFile(BaseModel):
    path: str
    content: str
    version: str
    """Changes whenever the file does. Send it back when saving to catch other edits."""


def _version(st: os.stat_result) -> str:
    return f"{st.st_mtime_ns}-{st.st_size}"


def _hidden(name: str, st: os.stat_result | None) -> bool:
    if name.startswith("."):
        return True
    attrs = getattr(st, "st_file_attributes", 0) if st else 0
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0))


def describe(root: Path, path: Path) -> FileEntry:
    """The entry at `path` (its parent already resolved inside `root`)."""
    is_link = path.is_symlink()
    try:
        st = path.stat()
    except OSError:
        st = None  # a broken link, or no permission
    if st is None:
        kind: EntryKind = "other"
    elif stat.S_ISDIR(st.st_mode):
        kind = "dir"
    elif stat.S_ISREG(st.st_mode):
        kind = "file"
    else:
        kind = "other"
    return FileEntry(
        name=path.name,
        path=relative(root, path),
        kind=kind,
        size=st.st_size if st and kind == "file" else None,
        modified=datetime.fromtimestamp(st.st_mtime, UTC) if st else None,
        is_link=is_link,
        hidden=_hidden(path.name, st),
    )


def list_dir(root: Path, folder: Path) -> Listing:
    if not folder.is_dir():
        raise (
            NotFound("That folder doesn't exist")
            if not folder.exists()
            else BadPath("That's a file, not a folder")
        )
    entries: list[FileEntry] = []
    truncated = False
    try:
        with os.scandir(folder) as it:
            for item in it:
                if item.name.startswith(UPLOAD_PREFIX):
                    continue
                if len(entries) >= MAX_ENTRIES:
                    truncated = True
                    break
                entries.append(describe(root, folder / item.name))
    except PermissionError as exc:
        raise FileError(f"No permission to read this folder ({exc.strerror})") from exc
    entries.sort(key=lambda e: (e.kind != "dir", e.name.casefold()))
    return Listing(path=relative(root, folder), entries=entries, truncated=truncated)


def read_text(root: Path, path: Path) -> TextFile:
    if not path.is_file():
        raise NotFound("That file doesn't exist")
    st = path.stat()
    if st.st_size > MAX_TEXT:
        raise FileError(f"Files over {MAX_TEXT // (1024 * 1024)} MB can't be opened here")
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        raise FileError("This isn't a text file")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FileError("This file isn't UTF-8 text") from exc
    return TextFile(path=relative(root, path), content=content, version=_version(st))


def write_text(root: Path, path: Path, content: str, version: str | None) -> TextFile:
    """Overwrite a text file in place (keeping its owner and mode)."""
    if not path.is_file():
        raise NotFound("That file doesn't exist")
    if version is not None and _version(path.stat()) != version:
        raise Conflict("The file changed since it was opened. Reload it and try again.")
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(content)
    return TextFile(path=relative(root, path), content=content, version=_version(path.stat()))


def make_dir(root: Path, path: Path) -> FileEntry:
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise Conflict(f"{path.name} already exists") from exc
    return describe(root, path)


def rename(root: Path, path: Path, new_name: str) -> FileEntry:
    target = path.parent / new_name
    # A case-only rename ("a" → "A") is the same entry on case-insensitive disks.
    same = target.exists(follow_symlinks=False) and os.path.samestat(path.lstat(), target.lstat())
    if target.exists(follow_symlinks=False) and not same:
        raise Conflict(f"{new_name} already exists")
    path.rename(target)
    return describe(root, target)


def delete(path: Path, permanent: bool) -> None:
    if not permanent:
        try:
            send2trash(path)
        except TrashPermissionError as exc:
            raise FileError(
                "Couldn't move this to the trash here. Delete it permanently instead."
            ) from exc
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def transfer(
    op: Literal["copy", "move"], source: Path, dest_dir: Path, on_conflict: OnConflict
) -> Path | None:
    """Copy or move `source` into `dest_dir`. None means skipped (name taken).

    Links are copied as links, so a copy never pulls in files from outside a location.
    """
    if source.is_dir() and not source.is_symlink() and inside(source.resolve(), dest_dir):
        raise BadPath(f"Can't {op} {source.name} into itself")
    name = source.name
    target = dest_dir / name
    if target.exists(follow_symlinks=False):
        if op == "move" and os.path.samestat(source.lstat(), target.lstat()):
            raise BadPath(f"{name} is already in that folder")
        if on_conflict == "skip":
            return None
        if on_conflict == "rename":
            target = dest_dir / available_name(dest_dir, name)
        elif target.is_dir() and not target.is_symlink():
            raise Conflict(f"A folder named {name} is already there; it isn't replaced")
        elif source.is_dir() and not source.is_symlink():
            raise Conflict(f"A file named {name} is already there; it isn't replaced")
    if op == "move":
        if target.exists(follow_symlinks=False):
            target.unlink()
        shutil.move(source, target)
    elif source.is_dir() and not source.is_symlink():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target, follow_symlinks=False)
    return target


# --- Uploads ---------------------------------------------------------------------------


def upload_part(folder: Path, upload_id: str) -> Path:
    return folder / f"{UPLOAD_PREFIX}{upload_id}"


def clear_stale_uploads(folder: Path) -> None:
    cutoff = time.time() - STALE_UPLOAD_SECONDS
    for part in folder.glob(f"{UPLOAD_PREFIX}*"):
        try:
            if part.lstat().st_mtime < cutoff:
                part.unlink()
        except OSError:
            pass


def finish_upload(part: Path, target: Path, overwrite: bool) -> None:
    if target.exists(follow_symlinks=False):
        if not overwrite:
            part.unlink(missing_ok=True)
            raise Conflict(f"{target.name} already exists")
        if target.is_dir() and not target.is_symlink():
            part.unlink(missing_ok=True)
            raise Conflict(f"A folder named {target.name} is already there")
    os.replace(part, target)


# --- Folder downloads ------------------------------------------------------------------


class _Sink(io.RawIOBase):
    """Collects what ZipFile writes so it can be streamed out piece by piece."""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        self._chunks.append(bytes(b))
        return len(b)

    def take(self) -> bytes:
        data = b"".join(self._chunks)
        self._chunks.clear()
        return data


def zip_folder(root: Path, folder: Path, base: str) -> Iterator[bytes]:
    """A zip of `folder`, streamed as it's built. Files are stored, not compressed: most
    large files (media, archives) are compressed already, and this keeps it fast.

    Links are followed only when they stay inside the location; unreadable files are
    skipped.
    """
    sink = _Sink()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_STORED) as zf:
        for dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
            current = Path(dirpath)
            dirnames[:] = [d for d in dirnames if not (current / d).is_symlink()]
            arc_dir = Path(base, current.relative_to(folder))
            if not filenames and not dirnames:
                zf.writestr(arc_dir.as_posix() + "/", b"")
            for name in filenames:
                if name.startswith(UPLOAD_PREFIX):
                    continue
                path = current / name
                try:
                    real = path.resolve()
                    if not inside(root, real) or not real.is_file():
                        continue
                    info = zipfile.ZipInfo.from_file(real, (arc_dir / name).as_posix())
                    with real.open("rb") as src, zf.open(info, "w") as dst:
                        while chunk := src.read(CHUNK):
                            dst.write(chunk)
                            if data := sink.take():
                                yield data
                except OSError as exc:
                    log.warning("zip: skipping %s: %s", path, exc)
    if data := sink.take():
        yield data
