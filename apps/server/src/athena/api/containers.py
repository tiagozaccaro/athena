"""Containers on the detected runtime. All routes need a session (see main.py)."""

import asyncio
import contextlib
import json
import subprocess
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from athena import audit
from athena.api.jobs import SSE_HEADERS
from athena.auth.deps import Authed, DbSession
from athena.containers import service
from athena.containers.runtime import (
    Runtime,
    RuntimeUnavailableError,
    runtime_from,
    start_command,
)
from athena.containers.service import (
    CONTAINER_REF,
    ContainerError,
    ContainerNotFoundError,
    ContainerOut,
)
from athena.jobs import Job, JobManager, JobOut, run_or_fail
from athena.platform.store import CapabilityStore

router = APIRouter(prefix="/containers", tags=["containers"])

ContainerRef = Annotated[str, Path(pattern=CONTAINER_REF, max_length=255)]


async def get_runtime(request: Request) -> Runtime:
    store: CapabilityStore = request.app.state.capabilities
    manifest = await store.get()
    try:
        return runtime_from(manifest.get("containers"))
    except RuntimeUnavailableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]


async def _call(fn, *args):
    """Run a blocking container call in a thread, mapping errors to HTTP."""
    try:
        return await asyncio.to_thread(fn, *args)
    except ContainerNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ContainerError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.get("", operation_id="listContainers")
async def list_containers(runtime: RuntimeDep) -> list[ContainerOut]:
    return await _call(service.list_containers, runtime)


@router.get("/{ref}", operation_id="getContainer")
async def get_container(ref: ContainerRef, runtime: RuntimeDep) -> ContainerOut:
    return await _call(service.get_container, runtime, ref)


async def _act(
    ref: str, action: service.Action, runtime: Runtime, user: Authed, db: DbSession
) -> ContainerOut:
    result = await _call(service.act, runtime, ref, action)
    audit.record(db, user.user.username, f"container.{action}", result.name)
    return result


@router.post("/{ref}/start", operation_id="startContainer")
async def start_container(
    ref: ContainerRef, runtime: RuntimeDep, user: Authed, db: DbSession
) -> ContainerOut:
    return await _act(ref, "start", runtime, user, db)


@router.post("/{ref}/stop", operation_id="stopContainer")
async def stop_container(
    ref: ContainerRef, runtime: RuntimeDep, user: Authed, db: DbSession
) -> ContainerOut:
    return await _act(ref, "stop", runtime, user, db)


@router.post("/{ref}/restart", operation_id="restartContainer")
async def restart_container(
    ref: ContainerRef, runtime: RuntimeDep, user: Authed, db: DbSession
) -> ContainerOut:
    return await _act(ref, "restart", runtime, user, db)


@router.delete("/{ref}", operation_id="removeContainer", status_code=status.HTTP_204_NO_CONTENT)
async def remove_container(
    ref: ContainerRef,
    runtime: RuntimeDep,
    user: Authed,
    db: DbSession,
    force: bool = False,
) -> None:
    name = (await _call(service.get_container, runtime, ref)).name
    await _call(service.remove, runtime, ref, force)
    audit.record(db, user.user.username, "container.remove", name, "forced" if force else None)


class LogsOut(BaseModel):
    lines: list[str]


@router.get("/{ref}/logs", operation_id="getContainerLogs")
async def get_logs(
    ref: ContainerRef,
    runtime: RuntimeDep,
    tail: Annotated[int, Query(ge=1, le=10_000)] = 200,
) -> LogsOut:
    return LogsOut(lines=await _call(service.logs, runtime, ref, tail))


@router.get(
    "/{ref}/logs/stream",
    operation_id="streamContainerLogs",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_logs(
    ref: ContainerRef,
    runtime: RuntimeDep,
    tail: Annotated[int, Query(ge=0, le=10_000)] = 200,
) -> StreamingResponse:
    """Server-Sent Events: one `log` event per line, following new output until disconnect."""
    await _call(service.get_container, runtime, ref)  # 404 before opening the stream
    argv = service.follow_logs_command(runtime, ref, tail)

    async def events() -> AsyncIterator[str]:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            assert proc.stdout is not None
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip("\r\n")
                yield f"event: log\ndata: {json.dumps(line)}\n\n"
            yield "event: end\ndata: {}\n\n"
        finally:
            # The client went away (or the container stopped): don't leave `logs -f` running.
            if proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


# ---------------------------------------------------------------- runtime


runtime_router = APIRouter(prefix="/containers/runtime", tags=["containers"])


@runtime_router.post(
    "/start", operation_id="startContainerRuntime", status_code=status.HTTP_202_ACCEPTED
)
async def start_runtime(request: Request, user: Authed, db: DbSession) -> JobOut:
    """Start a stopped runtime (e.g. `colima start`). Follow progress at /api/jobs/{id}/events."""
    store: CapabilityStore = request.app.state.capabilities
    manifest = await store.get()
    capability = manifest.get("containers")
    argv = start_command(capability, manifest.os)
    if argv is None or capability is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Athena can't start this runtime. "
            + (capability.detail if capability and capability.detail else ""),
        )
    jobs: JobManager = request.app.state.jobs

    async def body(job: Job) -> None:
        await run_or_fail(job, argv, f"Starting {capability.provider}")
        await job.log("Re-detecting capabilities…")
        refreshed = await store.refresh()
        containers = refreshed.get("containers")
        if containers is None or not containers.available:
            raise RuntimeError(
                "The runtime started, but Athena still can't reach it: "
                + (containers.detail if containers and containers.detail else "unknown")
            )
        await job.log(containers.detail or "Container runtime is ready")

    job = jobs.start(f"Start {capability.provider}", body)
    audit.record(db, user.user.username, "runtime.start", capability.provider)
    return job.out()
