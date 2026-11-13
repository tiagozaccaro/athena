from pathlib import Path

import pytest
from conftest import ADMIN, make_app, signed_in
from fastapi.testclient import TestClient

from athena.auth.service import LoginThrottle


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(make_app(tmp_path))


def test_first_run_requires_setup(client: TestClient) -> None:
    body = client.get("/api/auth/status").json()
    assert body == {"setup_required": True, "user": None, "csrf_token": None}


def test_protected_routes_need_a_session(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200  # public
    assert client.get("/api/system/info").status_code == 401
    assert client.get("/api/system/capabilities").status_code == 401
    assert client.post("/api/system/capabilities/refresh").status_code == 401


def test_setup_creates_admin_and_signs_in(client: TestClient) -> None:
    res = client.post("/api/auth/setup", json=ADMIN)
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["username"] == "admin"
    assert body["user"]["is_admin"] is True
    assert body["csrf_token"]
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/system/info").status_code == 200
    status = client.get("/api/auth/status").json()
    assert status["setup_required"] is False
    assert status["user"]["username"] == "admin"


def test_setup_only_works_once(client: TestClient) -> None:
    signed_in(client)
    res = client.post("/api/auth/setup", json={"username": "other", "password": "x" * 12})
    assert res.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "admin", "password": "short"},
        {"username": "a", "password": "long enough password"},
        {"username": "bad name!", "password": "long enough password"},
    ],
)
def test_setup_validates_input(client: TestClient, payload: dict) -> None:
    assert client.post("/api/auth/setup", json=payload).status_code == 422


def test_writes_require_csrf_header(client: TestClient) -> None:
    signed_in(client)
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/system/capabilities/refresh").status_code == 403
    res = client.post("/api/system/capabilities/refresh", headers={"X-CSRF-Token": "wrong"})
    assert res.status_code == 403
    res = client.post("/api/system/capabilities/refresh", headers={"X-CSRF-Token": token})
    assert res.status_code == 200


def test_login_and_logout(client: TestClient) -> None:
    signed_in(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/system/info").status_code == 401

    bad = client.post("/api/auth/login", json={**ADMIN, "password": "nope"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"username": "ghost", "password": "nope"})
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == bad.json()["detail"]  # no username enumeration

    good = client.post("/api/auth/login", json=ADMIN)
    assert good.status_code == 200
    assert good.json()["csrf_token"]
    assert client.get("/api/system/info").status_code == 200


def test_old_session_is_useless_after_logout(client: TestClient) -> None:
    signed_in(client)
    cookie = client.cookies.get("athena_session")
    client.post("/api/auth/logout")
    client.cookies.set("athena_session", cookie)
    assert client.get("/api/system/info").status_code == 401


def test_login_is_rate_limited(client: TestClient) -> None:
    signed_in(client)
    client.post("/api/auth/logout")
    for _ in range(5):
        assert client.post("/api/auth/login", json={**ADMIN, "password": "x"}).status_code == 401
    res = client.post("/api/auth/login", json=ADMIN)  # even the right password
    assert res.status_code == 429
    assert int(res.headers["Retry-After"]) > 0


def test_throttle_resets_after_success() -> None:
    throttle = LoginThrottle(limit=2, window=60)
    throttle.fail("ip")
    throttle.reset("ip")
    throttle.fail("ip")
    assert throttle.retry_after("ip") == 0
    throttle.fail("ip")
    assert throttle.retry_after("ip") > 0


def test_password_is_not_stored_in_plain_text(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    signed_in(TestClient(app))
    with app.state.db.engine.connect() as conn:
        stored = conn.exec_driver_sql("SELECT password_hash FROM users").scalar_one()
    assert ADMIN["password"] not in stored
    assert stored.startswith("$argon2id$")
