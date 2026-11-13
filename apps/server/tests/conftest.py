from pathlib import Path

from fake_probe import FakeProbe
from fastapi.testclient import TestClient

from athena.config import Settings
from athena.main import create_app
from athena.platform.detect import detect
from athena.platform.store import CapabilityStore

ADMIN = {"username": "admin", "password": "correct horse battery"}


def make_app(tmp_path: Path, web_dir: Path | None = None, store: CapabilityStore | None = None):
    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir or tmp_path / "no-web")
    store = store or CapabilityStore(detector=lambda: detect(FakeProbe(os="darwin")))
    return create_app(settings, capability_store=store)


def signed_in(client: TestClient) -> TestClient:
    """Create the admin (first run) and send the CSRF header on every request."""
    res = client.post("/api/auth/setup", json=ADMIN)
    assert res.status_code == 201, res.text
    client.headers["X-CSRF-Token"] = res.json()["csrf_token"]
    return client
