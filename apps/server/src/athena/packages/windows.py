"""Windows package managers: WinGet, Scoop and Chocolatey.

Athena runs as the logged-in user on Windows (docs/mvp-design.md §3, privilege model):
winget and Scoop install per user; Chocolatey installs machine-wide and needs an
elevated Athena. The fixtures for these are hand-written from the documented formats
(see tests/fixtures/packages/README.md).
"""

import asyncio
import json

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

# ------------------------------------------------------------------ WinGet

_WINGET_NONE = "No package found"
_WINGET_FLAGS = ["--accept-source-agreements", "--disable-interactivity"]


def _winget_rows(text: str) -> list[list[str]]:
    if _WINGET_NONE in text:
        return []
    # Footer lines ("1 upgrades available.") have no Id column.
    return [c for c in column_table(text, min_columns=4) if len(c) >= 3 and c[1]]


def parse_winget_search(text: str) -> list[PackageRef]:
    """Name, Id, Version, [Match,] Source. Columns are positional, so a localized
    header still parses."""
    out = []
    for cells in _winget_rows(text):
        out.append(
            PackageRef(
                name=cells[1],
                title=cells[0] or None,
                version=cells[2] or None,
                source=cells[-1] if len(cells) >= 4 else None,
            )
        )
    return out


def parse_winget_list(text: str) -> tuple[list[InstalledPackage], list[UpgradablePackage]]:
    """`winget list` / `winget upgrade`: Name, Id, Version, Available, Source."""
    installed, upgradable = [], []
    for cells in _winget_rows(text):
        cells = (cells + [""] * 5)[:5]
        title, pkg_id, version, available, source = cells
        installed.append(
            InstalledPackage(
                name=pkg_id, title=title or None, version=version or None, source=source or None
            )
        )
        if available:
            upgradable.append(
                UpgradablePackage(name=pkg_id, version=version or None, latest=available)
            )
    return installed, upgradable


class Winget(PackageManager):
    id = "winget"
    label = "WinGet"

    async def _read(self, argv: list[str], what: str) -> str:
        result = await self._run(argv, self.env)
        # winget exits non-zero when nothing matches; that's an empty list, not an error.
        if result.code != 0 and _WINGET_NONE not in result.stdout:
            raise PackageError(f"{what} failed: exit code {result.code}")
        return result.stdout

    async def search(self, query: str) -> list[PackageRef]:
        found, installed = await asyncio.gather(
            self._read(["winget", "search", "--query", query, *_WINGET_FLAGS], "winget search"),
            self.installed(),
        )
        results = parse_winget_search(found)[:SEARCH_LIMIT]
        names = {p.name for p in installed}
        for r in results:
            r.installed = r.name in names
        return results

    async def installed(self) -> list[InstalledPackage]:
        return parse_winget_list(
            await self._read(["winget", "list", *_WINGET_FLAGS], "winget list")
        )[0]

    async def upgradable(self) -> list[UpgradablePackage]:
        out = await self._read(["winget", "upgrade", *_WINGET_FLAGS], "winget upgrade")
        return parse_winget_list(out)[1]

    def _target(self, name: str) -> list[str]:
        return ["--id", name, "--exact", "--silent", *_WINGET_FLAGS]

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["winget", "install", *self._target(name), "--accept-package-agreements"]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["winget", "uninstall", *self._target(name)]

    def upgrade_argv(self, name: str | None) -> list[str]:
        if name:
            return ["winget", "upgrade", *self._target(name), "--accept-package-agreements"]
        return [
            "winget",
            "upgrade",
            "--all",
            "--silent",
            "--accept-package-agreements",
            *_WINGET_FLAGS,
        ]


# ------------------------------------------------------------------ Scoop


def parse_scoop_search(text: str) -> list[PackageRef]:
    """Name, Version, Source, Binaries (PowerShell table with a dashes row)."""
    return [
        PackageRef(name=c[0], version=c[1] or None, source=c[2] or None)
        for c in column_table(text, min_columns=3)
        if len(c) >= 3 and c[0]
    ]


def parse_scoop_export(text: str) -> list[InstalledPackage]:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise PackageError("scoop export returned something that isn't JSON") from exc
    return [
        InstalledPackage(name=a["Name"], version=a.get("Version"), source=a.get("Source"))
        for a in data.get("apps", [])
        if a.get("Name")
    ]


def parse_scoop_status(text: str) -> list[UpgradablePackage]:
    """Name, Installed Version, Latest Version, Missing Dependencies, Info."""
    return [
        UpgradablePackage(name=c[0], version=c[1] or None, latest=c[2] or None)
        for c in column_table(text, min_columns=3)
        if len(c) >= 3 and c[0] and c[2]
    ]


class Scoop(PackageManager):
    id = "scoop"
    label = "Scoop"
    can_refresh = True

    async def search(self, query: str) -> list[PackageRef]:
        found, installed = await asyncio.gather(
            self.run(["scoop", "search", query], "scoop search"), self.installed()
        )
        results = parse_scoop_search(found)[:SEARCH_LIMIT]
        names = {p.name for p in installed}
        for r in results:
            r.installed = r.name in names
        return results

    async def installed(self) -> list[InstalledPackage]:
        return parse_scoop_export(await self.run(["scoop", "export"], "scoop export"))

    async def upgradable(self) -> list[UpgradablePackage]:
        return parse_scoop_status(await self.run(["scoop", "status"], "scoop status"))

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["scoop", "install", f"{source}/{name}" if source else name]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["scoop", "uninstall", name]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return ["scoop", "update", name or "*"]

    def refresh_argv(self) -> list[str]:
        return ["scoop", "update"]


# ------------------------------------------------------------------ Chocolatey


def _pipe_rows(text: str, columns: int) -> list[list[str]]:
    rows = []
    for line in nonblank(text):
        cells = line.split("|")
        if len(cells) >= columns:
            rows.append([c.strip() for c in cells])
    return rows


def parse_choco_search(text: str) -> list[PackageRef]:
    return [PackageRef(name=c[0], version=c[1] or None) for c in _pipe_rows(text, 2)]


def parse_choco_list(text: str) -> list[InstalledPackage]:
    return [InstalledPackage(name=c[0], version=c[1] or None) for c in _pipe_rows(text, 2)]


def parse_choco_outdated(text: str) -> list[UpgradablePackage]:
    return [
        UpgradablePackage(name=c[0], version=c[1] or None, latest=c[2] or None)
        for c in _pipe_rows(text, 3)
    ]


class Choco(PackageManager):
    id = "choco"
    label = "Chocolatey"
    note = "Chocolatey installs for all users, so Athena must run as an administrator."
    _Y = ("-y", "--no-progress")

    async def search(self, query: str) -> list[PackageRef]:
        found, installed = await asyncio.gather(
            self.run(["choco", "search", query, "--limit-output"], "choco search"),
            self.installed(),
        )
        results = parse_choco_search(found)[:SEARCH_LIMIT]
        names = {p.name.lower() for p in installed}
        for r in results:
            r.installed = r.name.lower() in names
        return results

    async def installed(self) -> list[InstalledPackage]:
        return parse_choco_list(await self.run(["choco", "list", "--limit-output"], "choco list"))

    async def upgradable(self) -> list[UpgradablePackage]:
        # With enhanced exit codes on, 2 means "some packages are outdated".
        out = await self.run(["choco", "outdated", "--limit-output"], "choco outdated", (0, 2))
        return parse_choco_outdated(out)

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        return ["choco", "install", name, *self._Y]

    def uninstall_argv(self, name: str) -> list[str]:
        return ["choco", "uninstall", name, *self._Y]

    def upgrade_argv(self, name: str | None) -> list[str]:
        return ["choco", "upgrade", name or "all", *self._Y]
