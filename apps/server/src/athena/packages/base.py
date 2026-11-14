"""Shared pieces for package managers (docs/mvp-design.md §3, "Package managers per OS").

Every manager reads through `Runner` (so tests can replay recorded output) and parses
with pure functions that tests run against fixtures in tests/fixtures/packages/. Changes
(install, uninstall, upgrade, refresh) are argv lists that a job runs, streaming output.
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel

log = logging.getLogger(__name__)

READ_TIMEOUT = 120.0
SEARCH_LIMIT = 100

# Package names reach the CLI as one argv element (no shell), so the only risk is a name
# read as an option. Names start with a letter or digit; the rest covers apt (libc6:arm64,
# g++), brew taps (user/tap/formula), flatpak and winget ids (org.gnome.Calculator,
# Git.Git) and versions some managers put in names (python3.12).
PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:@/~-]{0,199}$")
SEARCH_QUERY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+:@/~-]{0,99}$")


class PackageRef(BaseModel):
    """A search result."""

    name: str
    """What install/uninstall take (a flatpak or winget id, a brew token)."""
    title: str | None = None
    """A display name when it differs from `name` (flatpak, winget, brew casks)."""
    version: str | None = None
    description: str | None = None
    source: str | None = None
    """Where it comes from, when the manager has several (flatpak remote, brew cask)."""
    installed: bool = False


class InstalledPackage(BaseModel):
    name: str
    title: str | None = None
    version: str | None = None
    description: str | None = None
    source: str | None = None


class UpgradablePackage(BaseModel):
    name: str
    version: str | None = None
    """The installed version."""
    latest: str | None = None


@dataclass(frozen=True)
class CmdResult:
    code: int
    stdout: str
    stderr: str


Runner = Callable[[list[str], Mapping[str, str] | None], Awaitable[CmdResult]]


class PackageError(RuntimeError):
    """A read command failed; the message is meant for the user."""


def command_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment for package commands: English, uncolored, non-interactive output."""
    env = dict(os.environ)
    if sys.platform != "win32":
        # Parsers expect English headers and messages. C.UTF-8 keeps non-ASCII intact.
        env["LC_ALL"] = "C.UTF-8"
        env["LANG"] = "C.UTF-8"
    env["NO_COLOR"] = "1"
    env.update(extra or {})
    return env


def resolve(argv: list[str]) -> list[str]:
    """Use the executable's full path. On Windows this finds .cmd shims (Scoop), which
    launching by bare name doesn't."""
    path = shutil.which(argv[0])
    return [path, *argv[1:]] if path else argv


async def run_command(argv: list[str], env: Mapping[str, str] | None = None) -> CmdResult:
    """The real runner: no shell, no stdin, a timeout, never raises for a bad exit code."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *resolve(argv),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            env=command_env(env),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        return CmdResult(-1, "", str(exc))
    try:
        out, err = await asyncio.wait_for(proc.communicate(), READ_TIMEOUT)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return CmdResult(-1, "", f"{argv[0]} took longer than {int(READ_TIMEOUT)} s")
    return CmdResult(
        proc.returncode or 0,
        out.decode(errors="replace"),
        err.decode(errors="replace"),
    )


def error_text(result: CmdResult, what: str) -> str:
    detail = (result.stderr.strip() or result.stdout.strip()).splitlines()
    tail = detail[-1] if detail else f"exit code {result.code}"
    return f"{what} failed: {tail}"


class PackageManager:
    """One package manager. Subclasses set the class attributes and implement the reads."""

    id: ClassVar[str]
    label: ClassVar[str]
    env: ClassVar[dict[str, str]] = {}
    can_upgrade_one: ClassVar[bool] = True
    """False where only a full upgrade is safe (pacman)."""
    can_refresh: ClassVar[bool] = False
    """True when package lists can be refreshed separately (apt update)."""
    note: ClassVar[str | None] = None
    """Shown in the UI, e.g. that installs on Arch also upgrade the system."""

    def __init__(self, run: Runner = run_command) -> None:
        self._run = run

    async def run(self, argv: list[str], what: str, ok_codes: tuple[int, ...] = (0,)) -> str:
        result = await self._run(argv, self.env)
        if result.code not in ok_codes:
            raise PackageError(error_text(result, what))
        return result.stdout

    # -- reads (async: some managers need more than one command)

    async def search(self, query: str) -> list[PackageRef]:
        raise NotImplementedError

    async def installed(self) -> list[InstalledPackage]:
        raise NotImplementedError

    async def upgradable(self) -> list[UpgradablePackage]:
        raise NotImplementedError

    # -- changes (run as jobs)

    def install_argv(self, name: str, source: str | None = None) -> list[str]:
        raise NotImplementedError

    def uninstall_argv(self, name: str) -> list[str]:
        raise NotImplementedError

    def upgrade_argv(self, name: str | None) -> list[str]:
        """Upgrade one package, or everything when `name` is None."""
        raise NotImplementedError

    def refresh_argv(self) -> list[str] | None:
        return None


# ------------------------------------------------------------------ parsing helpers


def nonblank(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def column_table(text: str, min_columns: int = 2) -> list[list[str]]:
    """Rows of a column-aligned table (snap, winget, scoop), as lists of cell strings.

    Finds the header (the first line followed by a dashes line, or the first line with
    enough words when there is no dashes line), takes column starts from where the
    dash groups or header words begin, and slices each row at those positions.
    Columns are positional, so localized headers (winget) still work.
    """
    # Progress spinners end with \r: keep only what was printed last on each line.
    lines = [line.rsplit("\r", 1)[-1].rstrip() for line in text.splitlines()]
    header_at = None
    starts: list[int] = []
    for i, line in enumerate(lines[:-1]):
        nxt = lines[i + 1]
        if line.strip() and nxt.strip() and set(nxt.strip()) <= {"-", " "}:
            header_at = i
            groups = list(re.finditer(r"-+", nxt))
            if len(groups) >= min_columns:  # scoop: one dash group per column
                starts = [g.start() for g in groups]
            else:  # winget: one long dashes line; use the header words
                starts = [m.start() for m in re.finditer(r"(?<!\S)\S", line)]
            break
    if header_at is None:
        for i, line in enumerate(lines):
            words = list(re.finditer(r"\S+", line))
            if len(words) >= min_columns:
                header_at, starts = i, [w.start() for w in words]
                break
    if header_at is None:
        return []
    first = header_at + 1
    if first < len(lines) and lines[first].strip() and set(lines[first].strip()) <= {"-", " "}:
        first += 1
    rows = []
    for line in lines[first:]:
        if not line.strip():
            continue
        cells = []
        for j, start in enumerate(starts):
            end = starts[j + 1] if j + 1 < len(starts) else None
            cells.append(line[start:end].strip() if start < len(line) else "")
        rows.append(cells)
    return rows
