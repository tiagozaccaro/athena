"""Builds the capability manifest for the current host.

Each detector is a small function of a `Probe`, returns one `Capability`, and never
raises: a failed probe becomes `missing` (or `stopped`) with a `detail` string.
Only capabilities relevant to the host's OS are reported, so a Mac never sees apt.
"""

import logging
import platform
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

from athena.platform.capabilities import Capability, CapabilityManifest
from athena.platform.probe import Probe, os_version

log = logging.getLogger(__name__)

Detector = Callable[[Probe], Capability]

CONTAINERS = "containers"
CONTAINERS_LABEL = "Containers"


# ---------------------------------------------------------------- containers


def _engine(provider: str, version: str, where: str, endpoint: str | None) -> Capability:
    return Capability(
        id=CONTAINERS,
        label=CONTAINERS_LABEL,
        status="ready",
        provider=provider,
        detail=f"Engine {version} at {where}",
        endpoint=endpoint,
    )


def _no_runtime(detail: str) -> Capability:
    return Capability(
        id=CONTAINERS, label=CONTAINERS_LABEL, status="missing", detail=detail, actions=["setup"]
    )


def detect_containers_linux(probe: Probe) -> Capability:
    candidates = [
        ("docker-engine", "/var/run/docker.sock"),
        ("podman", "/run/podman/podman.sock"),
    ]
    for provider, sock in candidates:
        version = probe.docker_version(f"unix://{sock}")
        if version:
            return _engine(provider, version, sock, f"unix://{sock}")
    if probe.which("dockerd") or probe.exists("/var/run/docker.sock"):
        return Capability(
            id=CONTAINERS,
            label=CONTAINERS_LABEL,
            status="stopped",
            provider="docker-engine",
            detail="Docker Engine is installed but not responding",
            actions=["start"],
        )
    if probe.which("podman"):
        return Capability(
            id=CONTAINERS,
            label=CONTAINERS_LABEL,
            status="stopped",
            provider="podman",
            detail="Podman is installed, but its API socket isn't running "
            "(systemctl enable --now podman.socket)",
            actions=["start"],
        )
    return _no_runtime("No container engine found. Install Docker Engine or Podman.")


def detect_containers_darwin(probe: Probe) -> Capability:
    # Unix socket paths are always POSIX, even when tests build this plan on Windows.
    colima_sock = (probe.home() / ".colima" / "default" / "docker.sock").as_posix()
    if probe.which("colima"):
        version = probe.docker_version(f"unix://{colima_sock}")
        if version:
            return _engine("colima", version, colima_sock, f"unix://{colima_sock}")
        return Capability(
            id=CONTAINERS,
            label=CONTAINERS_LABEL,
            status="stopped",
            provider="colima",
            detail="Colima is installed but not running",
            actions=["start"],
        )
    if probe.which("podman"):
        result = probe.run(
            ["podman", "machine", "inspect", "--format", "{{.ConnectionInfo.PodmanSocket.Path}}"]
        )
        sock = result.first_line
        if result.ok and sock and (version := probe.docker_version(f"unix://{sock}")):
            return _engine("podman", version, sock, f"unix://{sock}")
        return Capability(
            id=CONTAINERS,
            label=CONTAINERS_LABEL,
            status="stopped",
            provider="podman",
            detail="Podman is installed but its machine isn't running",
            actions=["start"],
        )
    return _no_runtime(
        "Colima not found. Install it with: brew install colima docker docker-compose"
    )


def detect_containers_windows(probe: Probe) -> Capability:
    # Preference order from the design: Docker Engine in WSL2, Podman, Rancher Desktop.
    if probe.which("wsl"):
        result = probe.run(
            ["wsl.exe", "-e", "sh", "-c", "docker version --format '{{.Server.Version}}'"],
            timeout=10,
        )
        if result.ok and result.first_line:
            # No socket reachable from Windows: commands go through `wsl.exe -e docker`.
            return _engine("wsl-docker", result.first_line, "the default WSL distro", None)
    version = probe.docker_version("npipe:////./pipe/podman-machine-default")
    if version:
        return _engine(
            "podman",
            version,
            r"\\.\pipe\podman-machine-default",
            "npipe:////./pipe/podman-machine-default",
        )
    version = probe.docker_version("npipe:////./pipe/docker_engine")
    if version:
        provider = "rancher-desktop" if probe.which("rdctl") else "docker-engine"
        return _engine(
            provider, version, r"\\.\pipe\docker_engine", "npipe:////./pipe/docker_engine"
        )
    if probe.which("podman") or probe.which("rdctl"):
        return Capability(
            id=CONTAINERS,
            label=CONTAINERS_LABEL,
            status="stopped",
            provider="podman" if probe.which("podman") else "rancher-desktop",
            detail="A container runtime is installed but not running",
            actions=["start"],
        )
    return _no_runtime(
        "No container runtime found. Install Docker Engine in WSL2, Podman, or Rancher Desktop."
    )


# ---------------------------------------------------------------- package managers


@dataclass(frozen=True)
class PackageManagerSpec:
    id: str
    label: str
    binary: str
    version_args: tuple[str, ...] = ("--version",)
    system_wide: bool = False
    """Needs root on Linux (installs into the system)."""


LINUX_PACKAGE_MANAGERS = [
    PackageManagerSpec("apt", "APT", "apt-get", system_wide=True),
    PackageManagerSpec("dnf", "DNF", "dnf", system_wide=True),
    PackageManagerSpec("pacman", "pacman", "pacman", system_wide=True),
    PackageManagerSpec("zypper", "zypper", "zypper", system_wide=True),
    PackageManagerSpec("apk", "apk", "apk", system_wide=True),
    PackageManagerSpec("flatpak", "Flatpak", "flatpak"),
    PackageManagerSpec("snap", "Snap", "snap", system_wide=True),
    PackageManagerSpec("brew", "Homebrew", "brew"),
]
DARWIN_PACKAGE_MANAGERS = [PackageManagerSpec("brew", "Homebrew", "brew")]
WINDOWS_PACKAGE_MANAGERS = [
    PackageManagerSpec("winget", "WinGet", "winget"),
    PackageManagerSpec("scoop", "Scoop", "scoop"),
    PackageManagerSpec("choco", "Chocolatey", "choco"),
]


def detect_package_manager(spec: PackageManagerSpec, probe: Probe) -> Capability:
    cap_id = f"packages.{spec.id}"
    path = probe.which(spec.binary)
    if not path:
        return Capability(id=cap_id, label=spec.label, status="missing", provider=spec.id)
    version = probe.run([path, *spec.version_args]).first_line or None
    if probe.os == "linux" and spec.system_wide and not probe.is_root():
        return Capability(
            id=cap_id,
            label=spec.label,
            status="needs_privilege",
            provider=spec.id,
            detail="Athena must run as root to install system packages",
        )
    if spec.id == "brew" and probe.is_root():
        return Capability(
            id=cap_id,
            label=spec.label,
            status="needs_privilege",
            provider=spec.id,
            detail="Homebrew refuses to run as root",
        )
    return Capability(id=cap_id, label=spec.label, status="ready", provider=spec.id, detail=version)


# ---------------------------------------------------------------- other capabilities


def detect_terminal(probe: Probe) -> Capability:
    if probe.os == "windows":
        # ConPTY arrived in Windows 10 1809 (build 17763).
        if probe.windows_build() >= 17763:
            return Capability(
                id="terminal.host", label="Terminal", status="ready", provider="conpty"
            )
        return Capability(
            id="terminal.host",
            label="Terminal",
            status="unsupported",
            detail="Needs Windows 10 1809 or later",
        )
    return Capability(id="terminal.host", label="Terminal", status="ready", provider="pty")


def detect_rclone(probe: Probe) -> Capability:
    path = probe.which("rclone")
    if not path:
        return Capability(
            id="cloud.rclone",
            label="Cloud storage",
            status="missing",
            provider="rclone",
            detail="rclone not found",
            actions=["setup"],
        )
    version = probe.run([path, "version"]).first_line or None
    return Capability(
        id="cloud.rclone", label="Cloud storage", status="ready", provider="rclone", detail=version
    )


def detect_builtin(probe: Probe) -> list[Capability]:
    return [
        Capability(id="files", label="Files", status="ready", provider="builtin"),
        Capability(id="shares.webdav", label="WebDAV shares", status="ready", provider="wsgidav"),
    ]


# ---------------------------------------------------------------- manifest


def detectors_for(probe: Probe) -> list[Detector]:
    containers: Detector = {
        "linux": detect_containers_linux,
        "darwin": detect_containers_darwin,
        "windows": detect_containers_windows,
    }[probe.os]
    managers = {
        "linux": LINUX_PACKAGE_MANAGERS,
        "darwin": DARWIN_PACKAGE_MANAGERS,
        "windows": WINDOWS_PACKAGE_MANAGERS,
    }[probe.os]
    package_detectors: list[Detector] = [
        (lambda p, spec=spec: detect_package_manager(spec, p)) for spec in managers
    ]
    return [containers, *package_detectors, detect_terminal, detect_rclone]


def _safe(detector: Detector, probe: Probe) -> Capability | None:
    try:
        return detector(probe)
    except Exception:  # a detector bug must not break the whole manifest
        log.exception("capability detector %s failed", getattr(detector, "__name__", detector))
        return None


def detect(probe: Probe | None = None) -> CapabilityManifest:
    probe = probe or Probe()
    detectors = detectors_for(probe)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda d: _safe(d, probe), detectors))
    capabilities = [c for c in results if c is not None] + detect_builtin(probe)
    return CapabilityManifest(
        os=probe.os,
        os_version=os_version(probe.os),
        arch=platform.machine().lower(),
        detected_at=datetime.now(UTC),
        capabilities=capabilities,
    )
