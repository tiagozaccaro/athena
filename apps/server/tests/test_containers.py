import os
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import make_app, signed_in
from fake_probe import FakeProbe
from fastapi.testclient import TestClient

from athena.containers import service
from athena.containers.runtime import (
    Runtime,
    RuntimeUnavailableError,
    runtime_from,
    start_command,
)
from athena.containers.service import ContainerNotFoundError, ContainerOut, check_ref
from athena.platform.capabilities import Capability
from athena.platform.detect import detect
from athena.platform.store import CapabilityStore


def cap(**kw) -> Capability:
    base = {"id": "containers", "label": "Containers", "status": "ready"}
    return Capability(**{**base, **kw})


# ---------------------------------------------------------------- runtime


def test_runtime_uses_docker_cli_with_the_detected_endpoint() -> None:
    rt = runtime_from(
        cap(provider="colima", endpoint="unix:///Users/me/.colima/default/docker.sock"),
        which=lambda b: f"/usr/bin/{b}" if b == "docker" else None,
    )
    assert rt.command("ps") == [
        "docker",
        "--host",
        "unix:///Users/me/.colima/default/docker.sock",
        "ps",
    ]


def test_runtime_for_docker_in_wsl() -> None:
    rt = runtime_from(cap(provider="wsl-docker"), which=lambda b: None)
    assert rt.cli == ("wsl.exe", "-e", "docker")


def test_runtime_falls_back_to_podman_cli() -> None:
    rt = runtime_from(
        cap(provider="podman", endpoint="unix:///run/podman/podman.sock"),
        which=lambda b: "/usr/bin/podman" if b == "podman" else None,
    )
    assert rt.cli == ("podman", "--url", "unix:///run/podman/podman.sock")


def test_runtime_requires_ready_capability() -> None:
    with pytest.raises(RuntimeUnavailableError, match="not running"):
        runtime_from(cap(status="stopped", detail="Colima is installed but not running"))
    with pytest.raises(RuntimeUnavailableError):
        runtime_from(None)
    with pytest.raises(RuntimeUnavailableError, match="no docker CLI"):
        runtime_from(cap(provider="colima", endpoint="unix:///x.sock"), which=lambda b: None)


@pytest.mark.parametrize(
    ("provider", "os_name", "expected"),
    [
        ("colima", "darwin", ["colima", "start"]),
        ("podman", "darwin", ["podman", "machine", "start"]),
        ("podman", "linux", ["systemctl", "enable", "--now", "podman.socket"]),
        ("docker-engine", "linux", ["systemctl", "start", "docker"]),
        ("rancher-desktop", "windows", ["rdctl", "start"]),
    ],
)
def test_start_commands(provider: str, os_name: str, expected: list[str]) -> None:
    assert start_command(cap(status="stopped", provider=provider, actions=["start"]), os_name) == (
        expected
    )


def test_no_start_command_without_start_action() -> None:
    assert start_command(cap(status="missing", actions=["setup"]), "darwin") is None


# ---------------------------------------------------------------- service helpers


def test_refs_starting_with_a_dash_are_rejected() -> None:
    assert check_ref("freshrss-db") == "freshrss-db"
    for bad in ["--privileged", "-f", "a b", "", "a/b"]:
        with pytest.raises(ContainerNotFoundError):
            check_ref(bad)


def test_to_out_maps_compose_labels_and_ports() -> None:
    fake = SimpleNamespace(
        id="9d537ba181b6aaaaaaaa",
        name="freshrss",
        config=SimpleNamespace(
            image="freshrss/freshrss:latest",
            labels={
                "com.docker.compose.project": "freshrss",
                "com.docker.compose.service": "app",
            },
        ),
        state=SimpleNamespace(
            status="running", running=True, exit_code=0, started_at=datetime(2026, 1, 1, tzinfo=UTC)
        ),
        created=datetime(2026, 1, 1, tzinfo=UTC),
        network_settings=SimpleNamespace(
            ports={
                "80/tcp": [
                    {"HostIp": "0.0.0.0", "HostPort": "8080"},
                    {"HostIp": "::", "HostPort": "8080"},
                ],
                "443/tcp": None,
            }
        ),
    )
    out = service.to_out(fake)
    assert out.id == "9d537ba181b6"
    assert (out.project, out.service) == ("freshrss", "app")
    assert out.ports == ["8080→80/tcp"]
    assert out.exit_code is None


# ---------------------------------------------------------------- API


def ready_store() -> CapabilityStore:
    probe = FakeProbe(
        os="darwin",
        home_dir=Path("/Users/me"),
        binaries={"colima": "/opt/homebrew/bin/colima"},
        engines={"unix:///Users/me/.colima/default/docker.sock": "29.5.2"},
    )
    return CapabilityStore(detector=lambda: detect(probe))


SAMPLE = ContainerOut(
    id="abc123def456",
    name="web",
    image="nginx:1.29",
    state="running",
    exit_code=None,
    created=None,
    started_at=None,
    ports=["8080→80/tcp"],
    project="site",
    service="web",
)


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("athena.containers.runtime.shutil.which", lambda b: f"/usr/bin/{b}")
    return signed_in(TestClient(make_app(tmp_path, store=ready_store())))


def test_containers_409_when_runtime_not_ready(tmp_path: Path) -> None:
    client = signed_in(TestClient(make_app(tmp_path)))  # fake macOS host without Colima
    res = client.get("/api/containers")
    assert res.status_code == 409
    assert "Colima not found" in res.json()["detail"]


def test_list_containers(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "list_containers", lambda rt: [SAMPLE])
    res = api.get("/api/containers")
    assert res.status_code == 200
    assert res.json()[0]["name"] == "web"


def test_actions_are_audited(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_act(rt: Runtime, ref: str, action: str) -> ContainerOut:
        calls.append((ref, action))
        return SAMPLE

    monkeypatch.setattr(service, "act", fake_act)
    assert api.post("/api/containers/abc123def456/stop").status_code == 200
    assert calls == [("abc123def456", "stop")]
    app = api.app
    with app.state.db.engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT username, action, target FROM audit_log").one()
    assert tuple(row) == ("admin", "container.stop", "web")


def test_invalid_ref_is_rejected_before_the_cli(api: TestClient) -> None:
    assert api.post("/api/containers/--privileged/stop").status_code == 422


def test_not_found_maps_to_404(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(rt, ref):
        raise ContainerNotFoundError(f"No container {ref!r}")

    monkeypatch.setattr(service, "get_container", missing)
    assert api.get("/api/containers/nope").status_code == 404


def test_container_actions_need_csrf(api: TestClient) -> None:
    api.headers.pop("X-CSRF-Token")
    assert api.post("/api/containers/abc123def456/stop").status_code == 403


def test_start_runtime_when_nothing_to_start(tmp_path: Path) -> None:
    client = signed_in(TestClient(make_app(tmp_path)))  # Colima missing: only "setup"
    assert client.post("/api/containers/runtime/start").status_code == 409


# ---------------------------------------------------------------- real engine (opt-in)


def _real_runtime() -> Runtime | None:
    if os.environ.get("ATHENA_DOCKER_TESTS") != "1" or not shutil.which("docker"):
        return None
    try:
        return runtime_from(detect().get("containers"))
    except RuntimeUnavailableError:
        return None


@pytest.mark.skipif(
    _real_runtime() is None, reason="set ATHENA_DOCKER_TESTS=1 with a running engine"
)
def test_real_container_lifecycle() -> None:
    rt = _real_runtime()
    assert rt is not None
    name = f"athena-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        rt.command(
            "run", "-d", "--name", name, "busybox:1.37", "sh", "-c", "echo hello; sleep 300"
        ),
        check=True,
        capture_output=True,
    )
    try:
        names = [c.name for c in service.list_containers(rt)]
        assert name in names
        assert "hello" in service.logs(rt, name, tail=10)
        assert service.act(rt, name, "stop").state == "exited"
        assert service.act(rt, name, "start").state == "running"
    finally:
        service.remove(rt, name, force=True)
    assert name not in [c.name for c in service.list_containers(rt)]
