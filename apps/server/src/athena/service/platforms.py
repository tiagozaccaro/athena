"""Per-OS service definitions."""

import os
import plistlib
import sys
from pathlib import Path

from athena.config import DEFAULT_PORT, default_data_dir
from athena.service.plan import MakeDir, Plan, RemoveFile, Run, ServiceSpec, WriteFile

SERVICE_NAME = "athena"
LAUNCHD_LABEL = "io.github.tiagozaccaro.athena"
WINDOWS_TASK = "Athena"
SYSTEMD_UNIT = Path("/etc/systemd/system/athena.service")
# schtasks limits the /TR command line to 261 characters.
WINDOWS_TR_MAX = 261


class UnsupportedPlatformError(RuntimeError):
    pass


def _serve_args(spec: ServiceSpec, *, include_defaults: bool = True) -> list[str]:
    args = ["-m", "athena", "serve"]
    if include_defaults or spec.port != DEFAULT_PORT:
        args += ["--port", str(spec.port)]
    if include_defaults or spec.data_dir != default_data_dir():
        args += ["--data-dir", str(spec.data_dir)]
    return args


# ---------------------------------------------------------------- Linux (systemd)


def _systemd_quote(arg: str) -> str:
    if any(c in arg for c in ' "\\'):
        return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return arg


def systemd_unit(spec: ServiceSpec) -> str:
    exec_start = " ".join(_systemd_quote(a) for a in [str(spec.python), *_serve_args(spec)])
    return f"""[Unit]
Description=Athena home server
Documentation=https://github.com/tiagozaccaro/athena
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""


def _linux_install(spec: ServiceSpec) -> Plan:
    return Plan(
        f"Installing systemd service {SYSTEMD_UNIT.name}",
        [
            MakeDir(spec.data_dir),
            WriteFile(SYSTEMD_UNIT, systemd_unit(spec)),
            Run(["systemctl", "daemon-reload"]),
            Run(["systemctl", "enable", "--now", SERVICE_NAME]),
            # Pick up a new version when reinstalling over a running service.
            Run(["systemctl", "restart", SERVICE_NAME]),
        ],
    )


def _linux_uninstall() -> Plan:
    return Plan(
        f"Removing systemd service {SYSTEMD_UNIT.name}",
        [
            Run(["systemctl", "disable", "--now", SERVICE_NAME], ignore_errors=True),
            RemoveFile(SYSTEMD_UNIT),
            Run(["systemctl", "daemon-reload"]),
        ],
    )


def _linux_status() -> Plan:
    return Plan(
        "systemd service status", [Run(["systemctl", "status", "--no-pager", SERVICE_NAME])]
    )


# ---------------------------------------------------------------- macOS (launchd)


def launchd_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def launchd_plist(spec: ServiceSpec) -> str:
    logs = spec.data_dir / "logs"
    data = {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [str(spec.python), *_serve_args(spec)],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs / "athena.log"),
        "StandardErrorPath": str(logs / "athena.log"),
        # launchd starts with a minimal PATH; Colima and Docker live in Homebrew.
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONUNBUFFERED": "1",
        },
    }
    return plistlib.dumps(data).decode()


def _launchd_domain() -> str:
    getuid = getattr(os, "getuid", None)  # POSIX only; plans are also built in tests on Windows
    return f"gui/{getuid() if getuid else 0}"


def _darwin_install(spec: ServiceSpec) -> Plan:
    plist = launchd_plist_path()
    return Plan(
        f"Installing launchd agent {LAUNCHD_LABEL}",
        [
            MakeDir(spec.data_dir / "logs"),
            WriteFile(plist, launchd_plist(spec)),
            # Replace a previously loaded agent (fails harmlessly if none is loaded).
            Run(
                ["launchctl", "bootout", f"{_launchd_domain()}/{LAUNCHD_LABEL}"], ignore_errors=True
            ),
            Run(["launchctl", "bootstrap", _launchd_domain(), str(plist)]),
        ],
    )


def _darwin_uninstall() -> Plan:
    return Plan(
        f"Removing launchd agent {LAUNCHD_LABEL}",
        [
            Run(
                ["launchctl", "bootout", f"{_launchd_domain()}/{LAUNCHD_LABEL}"], ignore_errors=True
            ),
            RemoveFile(launchd_plist_path()),
        ],
    )


def _darwin_status() -> Plan:
    return Plan(
        "launchd agent status",
        [Run(["launchctl", "print", f"{_launchd_domain()}/{LAUNCHD_LABEL}"])],
    )


# ---------------------------------------------------------------- Windows (Task Scheduler)


def windows_task_command(spec: ServiceSpec) -> str:
    # pythonw.exe runs without a console window at logon.
    pythonw = spec.python.with_name("pythonw.exe")
    args = _serve_args(spec, include_defaults=False)
    command = " ".join([f'"{pythonw}"', *(f'"{a}"' if " " in a else a for a in args)])
    if len(command) > WINDOWS_TR_MAX:
        raise UnsupportedPlatformError(
            f"Scheduled Task command is {len(command)} characters; Windows allows "
            f"{WINDOWS_TR_MAX}. Install Athena to a shorter path or use the default data dir."
        )
    return command


def _windows_install(spec: ServiceSpec) -> Plan:
    return Plan(
        f"Installing Scheduled Task '{WINDOWS_TASK}' (starts at logon)",
        [
            MakeDir(spec.data_dir),
            Run(["schtasks", "/End", "/TN", WINDOWS_TASK], ignore_errors=True),
            Run(
                [
                    "schtasks",
                    "/Create",
                    "/TN",
                    WINDOWS_TASK,
                    "/TR",
                    windows_task_command(spec),
                    "/SC",
                    "ONLOGON",
                    "/RL",
                    "LIMITED",
                    "/F",
                ]
            ),
            Run(["schtasks", "/Run", "/TN", WINDOWS_TASK]),
        ],
    )


def _windows_uninstall() -> Plan:
    return Plan(
        f"Removing Scheduled Task '{WINDOWS_TASK}'",
        [
            Run(["schtasks", "/End", "/TN", WINDOWS_TASK], ignore_errors=True),
            Run(["schtasks", "/Delete", "/TN", WINDOWS_TASK, "/F"], ignore_errors=True),
        ],
    )


def _windows_status() -> Plan:
    return Plan(
        "Scheduled Task status",
        [Run(["schtasks", "/Query", "/TN", WINDOWS_TASK, "/V", "/FO", "LIST"])],
    )


# ---------------------------------------------------------------- dispatch


def _platform(platform: str | None) -> str:
    p = platform or sys.platform
    if p.startswith("linux"):
        return "linux"
    if p in ("darwin", "win32"):
        return p
    raise UnsupportedPlatformError(f"Service install isn't supported on {p}")


def build_install(spec: ServiceSpec, platform: str | None = None) -> Plan:
    return {"linux": _linux_install, "darwin": _darwin_install, "win32": _windows_install}[
        _platform(platform)
    ](spec)


def build_uninstall(platform: str | None = None) -> Plan:
    return {"linux": _linux_uninstall, "darwin": _darwin_uninstall, "win32": _windows_uninstall}[
        _platform(platform)
    ]()


def build_status(platform: str | None = None) -> Plan:
    return {"linux": _linux_status, "darwin": _darwin_status, "win32": _windows_status}[
        _platform(platform)
    ]()
