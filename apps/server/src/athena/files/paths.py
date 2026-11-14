"""Turning API paths into host paths without leaving a location.

The API names a file by a location id plus a path relative to it, always with `/`
separators ("photos/2024/a.jpg", "" for the location itself). Two ways to resolve:

- `resolve()` follows symlinks, for reading and listing: the real path must be inside
  the location's real path, so a link that points outside is refused.
- `entry()` resolves only the parent and keeps the last name as is, for acting on the
  entry itself (delete, rename, move): deleting a link removes the link, never what it
  points to, even when that is outside the location.
"""

import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
# Characters Windows can't store in a name. New names avoid them on every OS, so files
# made through Athena can be copied to any host. Existing names are read as they are.
WINDOWS_RESERVED = set('<>:"/\\|?*')
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)
}
UPLOAD_PREFIX = ".athena-upload-"


class FileError(Exception):
    """A file operation that can't be done; `status` is the HTTP status to answer with."""

    status = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BadPath(FileError):
    status = 400


class Forbidden(FileError):
    status = 403


class NotFound(FileError):
    status = 404


class Conflict(FileError):
    status = 409


def _check_segment(part: str) -> None:
    if part in ("", ".", "..") or "\0" in part or (WINDOWS and ("\\" in part or ":" in part)):
        raise BadPath(f"Invalid path segment: {part!r}")


def split(rel: str) -> list[str]:
    """The segments of an API path. Leading and trailing slashes are ignored."""
    rel = rel.strip("/")
    if not rel:
        return []
    parts = rel.split("/")
    for part in parts:
        _check_segment(part)
    return parts


def check_new_name(name: str) -> str:
    """A name for something Athena creates: one segment, valid on every OS."""
    if not name or len(name.encode()) > 255:
        raise BadPath("Names must be 1 to 255 bytes long")
    if name in (".", "..") or name.endswith((" ", ".")) or name != name.strip():
        raise BadPath("Names can't be . or .., or start or end with a space, or end with a dot")
    if any(c in WINDOWS_RESERVED or ord(c) < 32 for c in name):
        raise BadPath("Names can't contain control characters or any of < > : \" / \\ | ? *")
    if name.split(".")[0].upper() in WINDOWS_DEVICES:
        raise BadPath(f"{name} is a reserved name on Windows")
    if name.startswith(UPLOAD_PREFIX):
        raise BadPath("That name is reserved for uploads in progress")
    return name


def root_of(location_path: str) -> Path:
    """The real path of a location's folder."""
    root = Path(location_path).resolve()
    if not root.is_dir():
        raise NotFound(f"The location's folder doesn't exist: {location_path}")
    return root


def inside(root: Path, path: Path) -> bool:
    return path == root or path.is_relative_to(root)


def resolve(root: Path, rel: str) -> Path:
    """The real path for `rel`, following links. It may not exist yet."""
    path = root.joinpath(*split(rel)).resolve()
    if not inside(root, path):
        raise Forbidden("That path leads outside the location")
    return path


def entry(root: Path, rel: str) -> Path:
    """The entry `rel` names, with its parent resolved but the entry itself not followed."""
    parts = split(rel)
    if not parts:
        raise BadPath("This can't be done to the location itself")
    parent = resolve(root, "/".join(parts[:-1]))
    return parent / parts[-1]


def existing_entry(root: Path, rel: str) -> Path:
    path = entry(root, rel)
    if not path.exists(follow_symlinks=False):
        raise NotFound(f"Not found: {rel}")
    return path


def relative(root: Path, path: Path) -> str:
    """The API path of `path`, which must be inside `root` (its parent resolved)."""
    return path.relative_to(root).as_posix() if path != root else ""


def available_name(folder: Path, name: str) -> str:
    """`name`, or "name (1).ext", "name (2).ext"… if that is taken in `folder`."""
    if not (folder / name).exists(follow_symlinks=False):
        return name
    # The extension is after the last dot, but a leading dot (".bashrc") isn't one.
    stem, ext = name.rsplit(".", 1) if "." in name[1:] else (name, "")
    for i in range(1, 10_000):
        candidate = f"{stem} ({i}).{ext}" if ext else f"{stem} ({i})"
        if not (folder / candidate).exists(follow_symlinks=False):
            return candidate
    raise Conflict(f"Couldn't find a free name for {name}")
