import io
import plistlib
from pathlib import Path

import pytest

from athena.service import ServiceSpec, build_install, build_uninstall, execute
from athena.service.plan import MakeDir, Plan, RemoveFile, Run, WriteFile
from athena.service.platforms import (
    SYSTEMD_UNIT,
    UnsupportedPlatformError,
    launchd_plist,
    systemd_unit,
    windows_task_command,
)

SPEC = ServiceSpec(
    python=Path("/opt/athena/tools/athena-server/bin/python"),
    data_dir=Path("/var/lib/athena"),
    port=8420,
)


def test_systemd_unit_runs_athena_serve() -> None:
    unit = systemd_unit(SPEC)
    assert (
        "ExecStart=/opt/athena/tools/athena-server/bin/python -m athena serve "
        "--port 8420 --data-dir /var/lib/athena" in unit
    )
    assert "WantedBy=multi-user.target" in unit


def test_systemd_unit_quotes_paths_with_spaces() -> None:
    spec = ServiceSpec(python=SPEC.python, data_dir=Path("/srv/my data"), port=9000)
    assert '--data-dir "/srv/my data"' in systemd_unit(spec)


def test_linux_install_plan() -> None:
    plan = build_install(SPEC, platform="linux")
    assert WriteFile(SYSTEMD_UNIT, systemd_unit(SPEC)) in plan.steps
    assert Run(["systemctl", "enable", "--now", "athena"]) in plan.steps


def test_linux_uninstall_tolerates_missing_service() -> None:
    plan = build_uninstall(platform="linux")
    assert plan.steps[0] == Run(["systemctl", "disable", "--now", "athena"], ignore_errors=True)
    assert RemoveFile(SYSTEMD_UNIT) in plan.steps


def test_launchd_plist() -> None:
    spec = ServiceSpec(
        python=Path("/Users/me/.local/share/athena/tools/athena-server/bin/python"),
        data_dir=Path("/Users/me/Library/Application Support/Athena"),
        port=8420,
    )
    data = plistlib.loads(launchd_plist(spec).encode())
    assert data["ProgramArguments"][:4] == [str(spec.python), "-m", "athena", "serve"]
    assert data["RunAtLoad"] and data["KeepAlive"]
    assert "/opt/homebrew/bin" in data["EnvironmentVariables"]["PATH"]


def test_darwin_install_plan_bootstraps_agent() -> None:
    plan = build_install(SPEC, platform="darwin")
    argvs = [s.argv for s in plan.steps if isinstance(s, Run)]
    assert argvs[-1][:2] == ["launchctl", "bootstrap"]


def test_windows_task_uses_pythonw_and_skips_default_args() -> None:
    from athena.config import default_data_dir

    spec = ServiceSpec(
        python=Path("C:/Users/me/AppData/Local/Athena/app/tools/athena-server/Scripts/python.exe"),
        data_dir=default_data_dir(),
        port=8420,
    )
    command = windows_task_command(spec)
    assert "pythonw.exe" in command
    assert command.endswith("-m athena serve")


def test_windows_task_rejects_too_long_command() -> None:
    spec = ServiceSpec(
        python=Path("C:/" + "x" * 300 + "/python.exe"), data_dir=Path("C:/d"), port=1
    )
    with pytest.raises(UnsupportedPlatformError):
        windows_task_command(spec)


def test_unsupported_platform() -> None:
    with pytest.raises(UnsupportedPlatformError):
        build_uninstall(platform="freebsd14")


def test_execute_dry_run_changes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "unit.service"
    calls: list[list[str]] = []
    plan = Plan("test", [WriteFile(target, "x"), Run(["systemctl", "daemon-reload"])])
    out = io.StringIO()
    assert execute(plan, dry_run=True, runner=lambda a: calls.append(a) or 0, out=out) == 0
    assert not target.exists()
    assert calls == []
    assert "[dry-run] write" in out.getvalue()


def test_execute_runs_steps_and_stops_on_failure(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        calls.append(argv)
        return 1 if argv[0] == "fail" else 0

    plan = Plan(
        "test",
        [
            MakeDir(tmp_path / "d"),
            Run(["ignored"], ignore_errors=True),
            Run(["fail"]),
            WriteFile(tmp_path / "never", "x"),
        ],
    )
    assert execute(plan, runner=runner, out=io.StringIO()) == 1
    assert (tmp_path / "d").is_dir()
    assert not (tmp_path / "never").exists()
    assert calls == [["ignored"], ["fail"]]
