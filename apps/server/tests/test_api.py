from pathlib import Path

from fastapi.testclient import TestClient

from athena import __version__
from athena.config import Settings
from athena.main import create_app


def client(tmp_path: Path, web_dir: Path | None = None) -> TestClient:
    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir or tmp_path / "no-web")
    return TestClient(create_app(settings))


def test_health(tmp_path: Path) -> None:
    res = client(tmp_path).get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": __version__}


def test_system_info(tmp_path: Path) -> None:
    body = client(tmp_path).get("/api/system/info").json()
    assert body["os"] in {"linux", "darwin", "windows"}
    assert body["version"] == __version__
    assert body["arch"]
    assert body["hostname"]


def test_root_without_web_ui_explains_dev_setup(tmp_path: Path) -> None:
    res = client(tmp_path).get("/")
    assert res.status_code == 200
    assert "pnpm dev" in res.json()["detail"]


def test_serves_bundled_web_ui(tmp_path: Path) -> None:
    web = tmp_path / "web"
    (web / "settings").mkdir(parents=True)
    (web / "index.html").write_text("<h1>athena</h1>")
    (web / "settings" / "index.html").write_text("<h1>settings</h1>")
    c = client(tmp_path, web)
    assert "athena" in c.get("/").text
    assert "settings" in c.get("/settings/").text
    # API routes still win over the static mount.
    assert c.get("/api/health").json()["status"] == "ok"


def test_openapi_has_stable_operation_ids(tmp_path: Path) -> None:
    paths = client(tmp_path).get("/api/openapi.json").json()["paths"]
    assert paths["/api/health"]["get"]["operationId"] == "getHealth"
    assert paths["/api/system/info"]["get"]["operationId"] == "getSystemInfo"
