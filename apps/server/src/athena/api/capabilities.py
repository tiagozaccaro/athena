from fastapi import APIRouter, Request

from athena.platform.capabilities import CapabilityManifest
from athena.platform.store import CapabilityStore

router = APIRouter(tags=["system"])


def _store(request: Request) -> CapabilityStore:
    return request.app.state.capabilities


@router.get("/system/capabilities", operation_id="getCapabilities")
async def get_capabilities(request: Request) -> CapabilityManifest:
    """What this host supports. The UI and the assistant only offer what's `available`."""
    return await _store(request).get()


@router.post("/system/capabilities/refresh", operation_id="refreshCapabilities")
async def refresh_capabilities(request: Request) -> CapabilityManifest:
    """Re-run detection, e.g. after the user installs or starts a container runtime."""
    return await _store(request).refresh()
