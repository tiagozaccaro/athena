import os
import shutil
import sys
import time
import uuid
from pathlib import Path

import pytest
from conftest import make_app, signed_in
from fastapi.testclient import TestClient
from test_containers import SAMPLE, ready_store

import athena.api.apps as apps_api
from athena.apps.store import AppStore, InvalidComposeError, check_name, parse_compose
from athena.containers import service as containers_service
from athena.platform.store import CapabilityStore

COMPOSE = "services:\n  web:\n    image: nginx:1.29\n    ports: ['8080:80']\n"


# ---------------------------------------------------------------- store


def test_names() -> None:
    assert check_name("jellyfin") == "jellyfin"
    for bad in ["Jellyfin", "-x", "a b", "a/b", "", "x" * 64]:
        with pytest.raises(ValueError):
            check_name(bad)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("services: [", "Invalid YAML"),
        ("- a\n- b\n", "mapping"),
        ("version: '3'\n", "at least one service"),
        ("services:\n  web: {}\n", "needs an `image`"),
    ],
)
def test_parse_compose_errors(text: str, message: str) -> None:
    with pytest.raises(InvalidComposeError, match=message):
        parse_compose(text)


def test_write_keeps_previous_version_and_creates_data_dir(tmp_path: Path) -> None:
    store = AppStore(tmp_path)
    store.write("web", COMPOSE)
    store.write("web", COMPOSE.replace("1.29", "1.30"))
    assert "1.30" in store.read("web")
    assert "1.29" in (store.dir("web") / "compose.prev.yaml").read_text()
    assert (store.dir("web") / "data").is_dir()
    assert store.env("web")["ATHENA_APP_DATA"] == str(store.dir("web") / "data")


def test_remove_keeps_data_unless_asked(tmp_path: Path) -> None:
    store = AppStore(tmp_path)
    store.write("web", COMPOSE)
    (store.dir("web") / "data" / "db.sqlite").write_text("important")
    store.remove("web", delete_data=False)
    assert not store.compose_path("web").exists()
    assert (store.dir("web") / "data" / "db.sqlite").exists()
    store.remove("web", delete_data=True)
    assert not store.dir("web").exists()


def test_remove_tidies_empty_dirs(tmp_path: Path) -> None:
    store = AppStore(tmp_path)
    store.write("web", COMPOSE)
    store.remove("web", delete_data=False)
    assert not store.dir("web").exists()


# ---------------------------------------------------------------- API


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("athena.containers.runtime.shutil.which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr(containers_service, "list_containers", lambda rt: [SAMPLE])
    # Jobs run a harmless command instead of `docker compose …`.
    monkeypatch.setattr(
        apps_api,
        "compose",
        lambda runtime, name, path, *args: [sys.executable, "-c", f"print('compose {args[0]}')"],
    )
    with TestClient(make_app(tmp_path, store=ready_store())) as client:
        yield signed_in(client)


def wait(client: TestClient, job_id: str) -> dict:
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job didn't finish")


def test_create_deploys_and_lists(api: TestClient, tmp_path: Path) -> None:
    res = api.post("/api/apps", json={"name": "site", "compose": COMPOSE})
    assert res.status_code == 202
    job = wait(api, res.json()["id"])
    assert job["status"] == "succeeded"
    assert any("compose up" in line for line in job["lines"])
    assert (tmp_path / "data" / "apps" / "site" / "compose.yaml").read_text() == COMPOSE

    apps = api.get("/api/apps").json()
    assert apps[0]["name"] == "site"
    assert (apps[0]["status"], apps[0]["running"], apps[0]["total"]) == ("running", 1, 1)
    assert apps[0]["ports"] == ["8080→80/tcp"]
    assert (apps[0]["title"], apps[0]["icon"]) == (None, None)  # not from a catalog

    detail = api.get("/api/apps/site").json()
    assert detail["compose"] == COMPOSE
    assert detail["containers"][0]["name"] == "web"


def test_create_rejects_duplicates_and_bad_input(api: TestClient) -> None:
    wait(api, api.post("/api/apps", json={"name": "site", "compose": COMPOSE}).json()["id"])
    assert api.post("/api/apps", json={"name": "site", "compose": COMPOSE}).status_code == 409
    assert api.post("/api/apps", json={"name": "Bad Name", "compose": COMPOSE}).status_code == 422
    res = api.post("/api/apps", json={"name": "x", "compose": "services: {}"})
    assert res.status_code == 422


def test_one_job_per_app(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        apps_api,
        "compose",
        lambda runtime, name, path, *args: [sys.executable, "-c", "import time; time.sleep(1)"],
    )
    first = api.post("/api/apps", json={"name": "slow", "compose": COMPOSE})
    assert first.status_code == 202
    res = api.post("/api/apps/slow/restart")
    assert res.status_code == 409
    assert "busy" in res.json()["detail"]
    wait(api, first.json()["id"])
    assert api.post("/api/apps/slow/restart").status_code == 202


def test_actions_edit_and_delete_are_audited(api: TestClient, tmp_path: Path) -> None:
    wait(api, api.post("/api/apps", json={"name": "site", "compose": COMPOSE}).json()["id"])
    assert wait(api, api.post("/api/apps/site/update").json()["id"])["status"] == "succeeded"
    edited = COMPOSE.replace("1.29", "1.30")
    assert wait(api, api.put("/api/apps/site", json={"compose": edited}).json()["id"])[
        "status"
    ] == ("succeeded")
    assert "1.30" in api.get("/api/apps/site").json()["compose"]

    job = wait(api, api.delete("/api/apps/site").json()["id"])
    assert job["status"] == "succeeded"
    assert api.get("/api/apps/site").status_code == 404
    assert api.get("/api/apps").json() == []

    with api.app.state.db.engine.connect() as conn:
        actions = [r[0] for r in conn.exec_driver_sql("SELECT action FROM audit_log ORDER BY id")]
    assert actions == ["app.create", "app.update", "app.edit", "app.delete"]


def test_unknown_app_and_action(api: TestClient) -> None:
    assert api.get("/api/apps/nope").status_code == 404
    assert api.post("/api/apps/nope/start").status_code == 404
    assert api.post("/api/apps/nope/explode").status_code == 422


def test_convert_endpoint(api: TestClient) -> None:
    res = api.post("/api/apps/convert", json={"command": "docker run -p 80:80 --rm nginx"})
    assert res.status_code == 200
    body = res.json()
    assert body["service"] == "nginx"
    assert "80:80" in body["compose"]
    assert body["warnings"]
    assert api.post("/api/apps/convert", json={"command": "nginx"}).status_code == 422


def test_validate_reports_structural_errors_without_the_cli(api: TestClient) -> None:
    res = api.post("/api/apps/validate", json={"compose": "services: ["})
    assert res.json()["ok"] is False
    assert "Invalid YAML" in res.json()["errors"][0]


# ---------------------------------------------------------------- real engine (opt-in)


def _docker_ready() -> bool:
    from athena.containers.runtime import RuntimeUnavailableError, runtime_from
    from athena.platform.detect import detect

    if os.environ.get("ATHENA_DOCKER_TESTS") != "1" or not shutil.which("docker"):
        return False
    try:
        runtime_from(detect().get("containers"))
    except RuntimeUnavailableError:
        return False
    return True


@pytest.mark.skipif(not _docker_ready(), reason="set ATHENA_DOCKER_TESTS=1 with a running engine")
def test_real_app_lifecycle(tmp_path: Path) -> None:
    name = f"athena-test-{uuid.uuid4().hex[:8]}"
    compose = (
        "services:\n  box:\n    image: busybox:1.37\n"
        "    command: [sh, -c, 'echo started; sleep 300']\n"
        "    volumes: ['${ATHENA_APP_DATA}:/data']\n"
    )
    with TestClient(make_app(tmp_path, store=CapabilityStore())) as raw:
        client = signed_in(raw)
        assert client.post("/api/apps/validate", json={"compose": compose}).json()["ok"]
        bad = client.post("/api/apps/validate", json={"compose": compose + "    nope: 1\n"})
        assert bad.json()["ok"] is False

        try:
            job = wait_long(
                client, client.post("/api/apps", json={"name": name, "compose": compose})
            )
            assert job["status"] == "succeeded", job["lines"]
            app = client.get(f"/api/apps/{name}").json()
            assert (app["status"], app["total"]) == ("running", 1)

            job = wait_long(client, client.post(f"/api/apps/{name}/stop"))
            assert client.get(f"/api/apps/{name}").json()["status"] == "stopped"
        finally:
            job = wait_long(client, client.delete(f"/api/apps/{name}?delete_data=true"))
        assert job["status"] == "succeeded", job["lines"]
        assert client.get(f"/api/apps/{name}").status_code == 404


def wait_long(client: TestClient, res) -> dict:
    assert res.status_code == 202, res.text
    job_id = res.json()["id"]
    for _ in range(600):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.2)
    raise AssertionError("job didn't finish in 2 minutes")
