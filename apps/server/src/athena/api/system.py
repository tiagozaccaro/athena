"""Health and basic host information. Capabilities arrive in milestone M1."""

import platform
import socket
import sys
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from athena import __version__
from athena.auth.deps import require_user
from athena.monitor import HostMonitor, StatsSnapshot

router = APIRouter(tags=["system"])

OsName = Literal["linux", "darwin", "windows"]


class Health(BaseModel):
    status: Literal["ok"]
    version: str


class SystemInfo(BaseModel):
    version: str
    os: OsName
    os_version: str
    arch: str
    hostname: str
    python: str


def current_os() -> OsName:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "darwin"
    return "windows"


@router.get("/health", operation_id="getHealth")
def health() -> Health:
    return Health(status="ok", version=__version__)


@router.get("/system/info", operation_id="getSystemInfo", dependencies=[require_user])
def system_info() -> SystemInfo:
    os_name = current_os()
    if os_name == "darwin":
        os_version = f"macOS {platform.mac_ver()[0]}"
    elif os_name == "windows":
        os_version = f"Windows {platform.release()} ({platform.version()})"
    else:
        try:
            release = platform.freedesktop_os_release()
            os_version = release.get("PRETTY_NAME", f"Linux {platform.release()}")
        except OSError:
            os_version = f"Linux {platform.release()}"
    return SystemInfo(
        version=__version__,
        os=os_name,
        os_version=os_version,
        arch=platform.machine().lower(),
        hostname=socket.gethostname(),
        python=platform.python_version(),
    )


def _monitor(request: Request) -> HostMonitor:
    return request.app.state.monitor


@router.get("/system/stats", operation_id="getSystemStats", dependencies=[require_user])
async def system_stats(request: Request) -> StatsSnapshot:
    """Current host stats plus up to an hour of samples for sparklines."""
    return await _monitor(request).snapshot()


@router.get(
    "/system/stats/stream",
    operation_id="streamSystemStats",
    dependencies=[require_user],
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def stream_system_stats(request: Request) -> StreamingResponse:
    """Server-Sent Events: a `stats` event (`HostStats` JSON) after every new sample."""
    return StreamingResponse(
        _monitor(request).events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
