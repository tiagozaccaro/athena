"""Low-level, never-raising host probes.

Detection code only talks to the host through `Probe`, so tests can swap in a fake
and cover every OS from any OS.
"""

import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from athena.platform.capabilities import OsName

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5.0


@dataclass(frozen=True)
class RunResult:
    code: int
    """Exit code, or -1 if the command couldn't run or timed out."""
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.code == 0

    @property
    def first_line(self) -> str:
        return next((ln.strip() for ln in self.stdout.splitlines() if ln.strip()), "")


def current_os() -> OsName:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "darwin"
    return "windows"


def os_version(os_name: OsName) -> str:
    if os_name == "darwin":
        return f"macOS {platform.mac_ver()[0]}"
    if os_name == "windows":
        return f"Windows {platform.release()} (build {platform.version()})"
    try:
        return platform.freedesktop_os_release().get("PRETTY_NAME", f"Linux {platform.release()}")
    except OSError:
        return f"Linux {platform.release()}"


class Probe:
    """Real host access. Every method returns a value instead of raising."""

    def __init__(self) -> None:
        self.os: OsName = current_os()

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, argv: list[str], timeout: float = DEFAULT_TIMEOUT) -> RunResult:
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                stdin=subprocess.DEVNULL,
                # No console window flash when running under pythonw on Windows.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return RunResult(proc.returncode, proc.stdout, proc.stderr)
        except (OSError, subprocess.SubprocessError) as exc:
            log.debug("probe %s failed: %s", argv, exc)
            return RunResult(-1, "", str(exc))

    def exists(self, path: str | Path) -> bool:
        try:
            return Path(path).exists()
        except OSError:
            return False

    def home(self) -> Path:
        return Path.home()

    def is_root(self) -> bool:
        geteuid = getattr(os, "geteuid", None)
        return bool(geteuid and geteuid() == 0)

    def windows_build(self) -> int:
        try:
            return int(platform.version().split(".")[-1])
        except ValueError:
            return 0

    def docker_version(self, endpoint: str, timeout: float = 2.0) -> str | None:
        """Engine version from `GET /version` on a Docker-compatible API, or None.

        `endpoint` is `unix:///path/to.sock` or `npipe:////./pipe/name`. Docker Engine,
        Colima, Podman and Rancher Desktop all expose this API.
        """
        request = b"GET /version HTTP/1.0\r\nHost: docker\r\n\r\n"
        try:
            if endpoint.startswith("unix://"):
                af_unix = getattr(socket, "AF_UNIX", None)
                if af_unix is None:
                    return None
                with socket.socket(af_unix, socket.SOCK_STREAM) as sock:
                    sock.settimeout(timeout)
                    sock.connect(endpoint.removeprefix("unix://"))
                    sock.sendall(request)
                    raw = b""
                    while chunk := sock.recv(65536):
                        raw += chunk
            elif endpoint.startswith("npipe://"):
                pipe = endpoint.removeprefix("npipe://").replace("/", "\\")
                with open(pipe, "r+b", buffering=0) as handle:
                    handle.write(request)
                    raw = handle.read(65536)
            else:
                return None
        except OSError:
            return None
        _, _, body = raw.partition(b"\r\n\r\n")
        try:
            return str(json.loads(body)["Version"])
        except (ValueError, KeyError, TypeError):
            return None
