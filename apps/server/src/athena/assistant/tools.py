"""The assistant's tools: Athena's own service layer, filtered by the capability manifest
(docs/mvp-design.md §4.5). Part A has read-only tools only; nothing here changes the host.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from pydantic_ai import FunctionToolset, RunContext, ToolFailed
from sqlmodel import Session, select

from athena.containers import service as containers
from athena.containers.runtime import Runtime, RuntimeUnavailableError, runtime_from
from athena.containers.service import ContainerError
from athena.db.models import App
from athena.files import locations, ops
from athena.files.paths import FileError, resolve, root_of
from athena.platform.capabilities import CapabilityManifest

MAX_LOG_LINES = 300
MAX_LOG_CHARS = 20_000
MAX_FILE_ENTRIES = 200


@dataclass
class Deps:
    app: FastAPI
    db: Session
    username: str
    manifest: CapabilityManifest

    def request(self) -> Request:
        """A bare request whose `.app` is the server, for helpers written for routes."""
        return Request({"type": "http", "app": self.app, "headers": []})

    def runtime(self) -> Runtime:
        try:
            return runtime_from(self.manifest.get("containers"))
        except RuntimeUnavailableError as exc:
            raise ToolFailed(str(exc)) from exc


Ctx = RunContext[Deps]


# ---------------------------------------------------------------- always available


async def get_capabilities(ctx: Ctx) -> dict[str, Any]:
    """What this server is and what it can do: OS, and each feature with its status
    (ready, stopped, missing, unsupported, needs_privilege) and details."""
    m = ctx.deps.manifest
    return {
        "os": m.os,
        "os_version": m.os_version,
        "arch": m.arch,
        "capabilities": [
            {"id": c.id, "label": c.label, "status": c.status, "detail": c.detail}
            for c in m.capabilities
        ],
    }


async def get_system_stats(ctx: Ctx) -> dict[str, Any]:
    """Current host stats: CPU, memory, swap, network and disk rates, disks, load,
    temperatures and boot time. Rates are bytes per second; sizes are bytes."""
    monitor = ctx.deps.app.state.monitor
    snapshot = await monitor.snapshot()
    return snapshot.model_dump(exclude={"history"})


# ---------------------------------------------------------------- containers


async def list_apps(ctx: Ctx) -> list[dict[str, Any]]:
    """The apps Athena manages (compose projects), with status, running/total containers
    and published ports."""
    from athena.api.apps import _summarize

    rows = ctx.deps.db.exec(select(App).order_by(App.name)).all()
    if not rows:
        return []
    try:
        found = await asyncio.to_thread(containers.list_containers, ctx.deps.runtime())
    except ContainerError as exc:
        raise ToolFailed(str(exc)) from exc
    request = ctx.deps.request()
    return [
        _summarize(request, row, found).model_dump(
            mode="json", include={"name", "title", "status", "running", "total", "ports"}
        )
        for row in rows
    ]


async def app_logs(ctx: Ctx, name: str, lines: int = 100) -> dict[str, list[str]]:
    """The last `lines` log lines (at most 300) of each container in the app `name`."""
    lines = max(1, min(lines, MAX_LOG_LINES))
    if ctx.deps.db.exec(select(App).where(App.name == name)).first() is None:
        raise ToolFailed(f"No app named {name!r}. Call list_apps for the names.")
    runtime = ctx.deps.runtime()
    try:
        found = await asyncio.to_thread(containers.list_containers, runtime)
        out: dict[str, list[str]] = {}
        budget = MAX_LOG_CHARS
        for c in (c for c in found if c.project == name):
            got = await asyncio.to_thread(containers.logs, runtime, c.name, lines)
            kept: list[str] = []
            for line in reversed(got):  # keep the newest lines when over budget
                budget -= len(line) + 1
                if budget < 0:
                    break
                kept.append(line)
            out[c.name] = list(reversed(kept))
    except ContainerError as exc:
        raise ToolFailed(str(exc)) from exc
    if not out:
        raise ToolFailed(f"{name} has no containers (it isn't deployed).")
    return out


# ---------------------------------------------------------------- files


async def list_file_locations(ctx: Ctx) -> list[dict[str, Any]]:
    """The folders the file manager can browse, with their ids for list_files."""
    return [
        {"id": loc.id, "name": loc.name, "path": loc.path}
        for loc in locations.all_locations(ctx.deps.db)
    ]


async def list_files(ctx: Ctx, location_id: int, path: str = "") -> dict[str, Any]:
    """The entries of a folder inside a file location. `path` is relative to the
    location, with `/` separators; "" is the location itself. At most 200 entries."""
    try:
        loc = locations.get(ctx.deps.db, location_id)
        root = root_of(loc.path)
        listing = await asyncio.to_thread(ops.list_dir, root, resolve(root, path))
    except (FileError, OSError) as exc:
        raise ToolFailed(str(exc)) from exc
    entries = [
        e.model_dump(mode="json", include={"name", "kind", "size", "modified"})
        for e in listing.entries[:MAX_FILE_ENTRIES]
    ]
    return {
        "location": loc.name,
        "path": path,
        "entries": entries,
        "truncated": len(listing.entries) > MAX_FILE_ENTRIES,
    }


def toolset_for(manifest: CapabilityManifest) -> FunctionToolset[Deps]:
    """The tools this host supports right now."""
    tools: list[Any] = [get_capabilities, get_system_stats]
    cap = manifest.get("containers")
    if cap is not None and cap.available:
        tools += [list_apps, app_logs]
    files = manifest.get("files")
    if files is not None and files.available:
        tools += [list_file_locations, list_files]
    return FunctionToolset(tools)
