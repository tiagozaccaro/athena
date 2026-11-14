"""App-level package managers: Homebrew (macOS and Linux), Flatpak and Snap (Linux)."""

import asyncio
import json
import re
from typing import ClassVar

from athena.packages.base import (
    SEARCH_LIMIT,
    InstalledPackage,
    PackageError,
    PackageManager,
    PackageRef,
    UpgradablePackage,
    column_table,
    nonblank,
)

# ------------------------------------------------------------------ Homebrew

BREW_INFO_LIMIT = 30  # `brew info` adds versions and descriptions for the top results


def parse_brew_search(text: str) -> list[str]:
    """Names from `brew search` (piped: formulae, a blank line, then casks)."""
    return [line.strip() for line in nonblank(text) if not line.startswith("==>")]


def _json(text: str, what: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise PackageError(f"{what} returned something that isn't JSON") from exc
    return data if isinstance(data, dict) else {}


def parse_brew_info(text: str) -> list[PackageRef]:
    """`brew info --json=v2 names…` → search results with versions and descriptions."""
    data = _json(text, "brew info")
    out = []
    for f in data.get("formulae", []):
        out.append(
            PackageRef(
                name=f["name"],
                version=(f.get("versions") or {}).get("stable"),
                description=f.get("desc"),
                source="formula",
                installed=bool(f.get("installed")),
            )
        )
    for c in data.get("casks", []):
        names = c.get("name") or []
        out.append(
            PackageRef(
                name=c["token"],
                title=names[0] if names and names[0] != c["token"] else None,
                version=c.get("version"),
                description=c.get("desc"),
                source="cask",
                installed=bool(c.get("installed")),
            )
        )
    return out


def parse_brew_installed(text: str) -> list[InstalledPackage]:
    data = _json(text, "brew info")
    out = []
    for f in data.get("formulae", []):
        versions = [i.get("version") for i in f.get("installed") or [] if i.get("version")]
        out.append(
            InstalledPackage(
                name=f["name"],
                version=versions[-1] if versions else None,
                description=f.get("desc"),
                source="formula",
            )
        )
    for c in data.get("casks", []):
        names = c.get("name") or []
        installed = c.get("installed")
        out.append(
            InstalledPackage(
                name=c["token"],
                title=names[0] if names and names[0] != c["token"] else None,
                version=installed if isinstance(installed, str) else None,
                description=c.get("desc"),
                source="cask",
            )
        )
    return out


def parse_brew_outdated(text: str) -> list[UpgradablePackage]:
    data = _json(text, "brew outdated")
    out = []
    for item in [*data.get("formulae", []), *data.get("casks", [])]:
        installed = item.get("installed_versions") or []
        out.append(
            UpgradablePackage(
                name=item["name"],
                version=installed[-1] if installed else None,
                latest=item.get("current_version"),
            )
        )
    return out


class Brew(PackageManager):
    id = "brew"
    label = "Homebrew"
    can_refresh = True
    env: ClassVar[dict[str, str]] = {
        "NONINTERACTIVE": "1",
        "HOMEBREW_NO_ENV_HINTS": "1",
        "HOMEBREW_NO_COLOR": "1",
    }

    async def search(self, query: str) -> list[PackageRef]:
        # Exit code 1 means "no formulae or casks found".
        names = parse_brew_search(await self.run(["brew", "search", query], "brew search", (0, 1)))
        names = names[:SEARCH_LIMIT]
        if not names:
            return []
        top = names[:BREW_INFO_LIMIT]
        detailed = {
            r.name: r
            for r in parse_brew_info(
                await self.run(["brew", "info", "--json=v2", *top], "brew info")
            )
        }
        return [detailed.get(n) or PackageRef(name=n) for n in names]

    async def installed(self) -> list[InstalledPackage]:
        out = await self.run(["brew", "info", "--json=v2", "--installed"], "brew info")
        return parse_brew_installed(out)

    async def upgradable(self) -> list[UpgradablePackage]:
        return parse_brew_outdated(
            await self.run(["brew", "outdated", "--json=v2"], "brew outdated")
        )

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["brew", "install", *(["--cask"] if source == "cask" else []), name]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["brew", "uninstall", name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return ["brew", "upgrade", *([name] if name else [])]

    def refresh_argv(self) -> list[str]:
        return ["brew", "update"]


# ------------------------------------------------------------------ Flatpak


def parse_flatpak_search(text: str) -> list[PackageRef]:
    """`flatpak search --columns=application,name,version,description,remotes`."""
    out = []
    for line in nonblank(text):
        cells = line.split("\t")
        if len(cells) < 5:  # "No matches found"
            continue
        app_id, name, version, desc, remotes = cells[:5]
        out.append(
            PackageRef(
                name=app_id,
                title=name or None,
                version=version or None,
                description=desc or None,
                source=remotes.split(",")[0] or None,
            )
        )
    return out


def parse_flatpak_installed(text: str) -> list[InstalledPackage]:
    """`flatpak list --app --columns=application,name,version,origin`."""
    out = []
    for line in nonblank(text):
        cells = (line.split("\t") + [""] * 4)[:4]
        if cells[0]:
            out.append(
                InstalledPackage(
                    name=cells[0],
                    title=cells[1] or None,
                    version=cells[2] or None,
                    source=cells[3] or None,
                )
            )
    return out


def parse_flatpak_updates(text: str) -> list[UpgradablePackage]:
    """`flatpak remote-ls --updates --app --columns=application,version`."""
    out = []
    for line in nonblank(text):
        cells = [*line.split("\t"), ""][:2]
        if cells[0]:
            out.append(UpgradablePackage(name=cells[0], latest=cells[1] or None))
    return out


class Flatpak(PackageManager):
    id = "flatpak"
    label = "Flatpak"
    can_refresh = True
    _Y = ("-y", "--noninteractive")

    async def search(self, query: str) -> list[PackageRef]:
        cols = "--columns=application,name,version,description,remotes"
        results, installed = await asyncio.gather(
            self.run(["flatpak", "search", cols, query], "flatpak search"), self.installed()
        )
        found = parse_flatpak_search(results)[:SEARCH_LIMIT]
        names = {p.name for p in installed}
        for r in found:
            r.installed = r.name in names
        return found

    async def installed(self) -> list[InstalledPackage]:
        out = await self.run(
            ["flatpak", "list", "--app", "--columns=application,name,version,origin"],
            "flatpak list",
        )
        return parse_flatpak_installed(out)

    async def upgradable(self) -> list[UpgradablePackage]:
        out, installed = await asyncio.gather(
            self.run(
                ["flatpak", "remote-ls", "--updates", "--app", "--columns=application,version"],
                "flatpak remote-ls",
            ),
            self.installed(),
        )
        current = {p.name: p.version for p in installed}
        ups = parse_flatpak_updates(out)
        for u in ups:
            u.version = current.get(u.name)
        return ups

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["flatpak", "install", *self._Y, source or "flathub", name]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["flatpak", "uninstall", *self._Y, name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return ["flatpak", "update", *self._Y, *([name] if name else [])]

    def refresh_argv(self) -> list[str]:
        return ["flatpak", "update", "--appstream", "-y"]


# ------------------------------------------------------------------ Snap

_VERIFIED = re.compile(r"(\*\*|✓|✪)$")


def parse_snap_find(text: str) -> list[PackageRef]:
    """`snap find`: Name, Version, Publisher, Notes, Summary."""
    out = []
    for cells in column_table(text, min_columns=5):
        if len(cells) >= 5 and cells[0]:
            out.append(
                PackageRef(
                    name=cells[0],
                    version=cells[1] or None,
                    description=cells[4] or None,
                    source=_VERIFIED.sub("", cells[2]) or None,
                )
            )
    return out


def parse_snap_list(text: str) -> list[InstalledPackage]:
    """`snap list`: Name, Version, Rev, Tracking, Publisher, Notes."""
    out = []
    for cells in column_table(text, min_columns=5):
        if cells and cells[0]:
            out.append(
                InstalledPackage(
                    name=cells[0],
                    version=cells[1] or None,
                    source=_VERIFIED.sub("", cells[4]) if len(cells) > 4 else None,
                )
            )
    return out


def parse_snap_refresh_list(text: str) -> list[UpgradablePackage]:
    """`snap refresh --list`: Name, Version, Rev, Size, Publisher, Notes."""
    return [
        UpgradablePackage(name=cells[0], latest=cells[1] or None)
        for cells in column_table(text, min_columns=5)
        if cells and cells[0]
    ]


class Snap(PackageManager):
    id = "snap"
    label = "Snap"

    async def search(self, query: str) -> list[PackageRef]:
        found, installed = await asyncio.gather(
            self.run(["snap", "find", query], "snap find"), self.installed()
        )
        results = parse_snap_find(found)[:SEARCH_LIMIT]
        names = {p.name for p in installed}
        for r in results:
            r.installed = r.name in names
        return results

    async def installed(self) -> list[InstalledPackage]:
        return parse_snap_list(await self.run(["snap", "list"], "snap list"))

    async def upgradable(self) -> list[UpgradablePackage]:
        out, installed = await asyncio.gather(
            self.run(["snap", "refresh", "--list"], "snap refresh --list"), self.installed()
        )
        current = {p.name: p.version for p in installed}
        ups = parse_snap_refresh_list(out)
        for u in ups:
            u.version = current.get(u.name)
        return ups

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["snap", "install", name]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["snap", "remove", name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return ["snap", "refresh", *([name] if name else [])]
