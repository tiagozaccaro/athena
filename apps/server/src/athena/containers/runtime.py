"""Builds a client for the detected container runtime, and knows how to start one."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass

from python_on_whales import DockerClient

from athena.platform.capabilities import Capability

Which = Callable[[str], str | None]


class RuntimeUnavailableError(RuntimeError):
    """The containers capability isn't ready (stopped, missing or unsupported)."""


@dataclass(frozen=True)
class Runtime:
    provider: str
    cli: tuple[str, ...]
    """CLI argv prefix: ("docker", "--host", "unix:///…") or ("wsl.exe", "-e", "docker")."""

    def client(self, **kwargs) -> DockerClient:
        return DockerClient(client_call=list(self.cli), **kwargs)

    def command(self, *args: str) -> list[str]:
        return [*self.cli, *args]


def runtime_from(capability: Capability | None, which: Which | None = None) -> Runtime:
    # Looked up at call time (not as a default argument) so tests can patch shutil.which.
    which = which or shutil.which
    if capability is None or capability.status != "ready":
        detail = capability.detail if capability else "No container capability detected"
        raise RuntimeUnavailableError(detail or "Container runtime isn't ready")

    provider = capability.provider or "docker-engine"
    if provider == "wsl-docker":
        return Runtime(provider, ("wsl.exe", "-e", "docker"))

    endpoint = capability.endpoint
    if which("docker"):
        cli = ("docker", "--host", endpoint) if endpoint else ("docker",)
        return Runtime(provider, cli)
    if provider == "podman" and which("podman"):
        cli = ("podman", "--url", endpoint) if endpoint else ("podman",)
        return Runtime(provider, cli)
    raise RuntimeUnavailableError(
        "The container engine is running, but no docker CLI was found on PATH"
    )


def start_command(capability: Capability | None, os_name: str) -> list[str] | None:
    """The command that starts a stopped runtime, or None if Athena can't start it."""
    if capability is None or "start" not in capability.actions:
        return None
    provider = capability.provider or ""
    if provider == "podman":
        # Rootful Podman on Linux serves its API from a systemd socket; elsewhere it's a VM.
        if os_name == "linux":
            return ["systemctl", "enable", "--now", "podman.socket"]
        return ["podman", "machine", "start"]
    return {
        "colima": ["colima", "start"],
        "rancher-desktop": ["rdctl", "start"],
        "docker-engine": ["systemctl", "start", "docker"],
    }.get(provider)
