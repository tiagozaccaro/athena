"""File locations: the folders the file manager may reach (docs/mvp-design.md §4.3)."""

import os
import sys
from pathlib import Path

from sqlmodel import Session, select

from athena.db.models import FileLocation, SystemSetting
from athena.files.paths import BadPath, Conflict, NotFound

SEEDED_KEY = "files_defaults_seeded"


def default_locations(data_dir: Path) -> list[tuple[str, Path]]:
    """Home, and the folder that holds the apps' data.

    Linux runs Athena as a root service, where "home" would be /root; /home holds the
    people's folders there instead.
    """
    if sys.platform.startswith("linux") and os.geteuid() == 0:
        home = Path("/home")
    else:
        home = Path.home()
    found = [("Home", home)] if home.is_dir() else []
    return [*found, ("App data", data_dir / "apps")]


def seed_defaults(db: Session, data_dir: Path) -> None:
    """Add the default locations once, on the first start. Removing them sticks."""
    if db.get(SystemSetting, SEEDED_KEY) is not None:
        return
    for name, path in default_locations(data_dir):
        path.mkdir(parents=True, exist_ok=True)
        db.add(FileLocation(name=name, path=str(path.resolve())))
    db.add(SystemSetting(key=SEEDED_KEY, value="1"))
    db.commit()


def all_locations(db: Session) -> list[FileLocation]:
    return list(db.exec(select(FileLocation).order_by(FileLocation.id)))  # type: ignore[arg-type]


def get(db: Session, location_id: int) -> FileLocation:
    loc = db.get(FileLocation, location_id)
    if loc is None:
        raise NotFound("No such location")
    return loc


def checked_path(raw: str) -> str:
    """An absolute, existing folder, with `~` expanded and links resolved."""
    path = Path(raw.strip()).expanduser()
    if not path.is_absolute():
        raise BadPath("Use an absolute path, like /srv/media or D:\\Media")
    if not path.is_dir():
        raise BadPath(f"{path} isn't an existing folder")
    return str(path.resolve())


def save(db: Session, loc: FileLocation, name: str, path: str) -> FileLocation:
    name = name.strip()
    if not name:
        raise BadPath("Give the location a name")
    taken = db.exec(select(FileLocation).where(FileLocation.name == name)).first()
    if taken is not None and taken.id != loc.id:
        raise Conflict(f"A location named {name} already exists")
    loc.name = name
    loc.path = checked_path(path)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc
