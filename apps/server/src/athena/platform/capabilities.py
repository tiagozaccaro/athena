"""The capability manifest: what this host can do, as reported to the UI and the assistant."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, computed_field

OsName = Literal["linux", "darwin", "windows"]

Status = Literal["ready", "stopped", "missing", "unsupported", "needs_privilege"]
"""
- ready: usable now
- stopped: installed but not running (e.g. Colima not started); see `actions`
- missing: not installed; see `actions` (usually "setup")
- unsupported: can't work on this host
- needs_privilege: installed, but Athena's user can't use it (e.g. apt when not root)
"""

Action = Literal["start", "setup"]


class Capability(BaseModel):
    id: str
    """Dotted id, e.g. "containers", "packages.apt", "terminal.host"."""
    label: str
    status: Status
    provider: str | None = None
    """Which implementation backs it, e.g. "colima", "docker-engine", "winget"."""
    detail: str | None = None
    """Human-readable version or reason."""
    endpoint: str | None = None
    """How to reach it, e.g. a Docker API socket (unix:///…, npipe:////./pipe/…)."""
    actions: list[Action] = []

    @computed_field
    @property
    def available(self) -> bool:
        return self.status == "ready"


class CapabilityManifest(BaseModel):
    os: OsName
    os_version: str
    arch: str
    detected_at: datetime
    capabilities: list[Capability]

    def get(self, capability_id: str) -> Capability | None:
        return next((c for c in self.capabilities if c.id == capability_id), None)
