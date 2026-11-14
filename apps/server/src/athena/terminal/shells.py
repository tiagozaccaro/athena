"""What the terminal runs: the host's shell, or a shell inside a container."""

import os
import shutil
import sys
from pathlib import Path

from athena.containers.runtime import Runtime

# bash when the image has it, sh otherwise. Passed as one argument, so no host shell.
CONTAINER_SHELL = "if command -v bash >/dev/null 2>&1; then exec bash; else exec sh; fi"


def host_shell() -> list[str]:
    """The service user's login shell on POSIX; PowerShell 7 or Windows PowerShell."""
    if sys.platform == "win32":
        exe = shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"
        return [exe, "-NoLogo"]
    shell = ""
    try:
        import pwd

        shell = pwd.getpwuid(os.getuid()).pw_shell
    except (ImportError, KeyError):
        shell = os.environ.get("SHELL", "")
    if not shell or not os.access(shell, os.X_OK) or shell.endswith(("/nologin", "/false")):
        shell = "/bin/sh"
    return [shell, "-l"]


def container_shell(runtime: Runtime, ref: str) -> list[str]:
    """`docker exec -it` through the same CLI the rest of Athena uses (WSL included)."""
    return runtime.command(
        "exec", "-it", "-e", "TERM=xterm-256color", ref, "sh", "-c", CONTAINER_SHELL
    )


def shell_env() -> dict[str, str]:
    env = dict(os.environ)
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    if sys.platform != "win32":
        env.setdefault("LANG", "C.UTF-8")
    return env


def home() -> Path:
    try:
        return Path.home()
    except RuntimeError:
        return Path.cwd()
