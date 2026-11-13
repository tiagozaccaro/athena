import io
import json
from pathlib import Path

import pytest
from conftest import ADMIN, make_app, signed_in
from fastapi.testclient import TestClient

from athena.cli import main


def test_openapi_export_does_not_touch_the_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "real-data-dir"
    monkeypatch.setenv("ATHENA_DATA_DIR", str(data_dir))
    out = tmp_path / "openapi.json"
    assert main(["openapi", "--output", str(out)]) == 0
    assert "/api/auth/login" in json.loads(out.read_text())["paths"]
    assert not data_dir.exists()


NEW_PASSWORD = "a brand new password"


def reset(monkeypatch: pytest.MonkeyPatch, data_dir: Path, *args: str, password: str) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(password + "\n"))
    return main(["admin", "reset-password", "--data-dir", str(data_dir), "--password-stdin", *args])


def test_reset_password_replaces_it_and_signs_out_everywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = signed_in(TestClient(make_app(tmp_path)))
    assert client.get("/api/system/info").status_code == 200

    assert reset(monkeypatch, tmp_path / "data", password=NEW_PASSWORD) == 0
    assert "reset" in capsys.readouterr().out

    # The existing browser session is gone.
    assert client.get("/api/system/info").status_code == 401
    # Old password fails, new one works.
    assert client.post("/api/auth/login", json=ADMIN).status_code == 401
    ok = client.post("/api/auth/login", json={**ADMIN, "password": NEW_PASSWORD})
    assert ok.status_code == 200


def test_reset_password_rejects_short_passwords(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    signed_in(TestClient(make_app(tmp_path)))
    assert reset(monkeypatch, tmp_path / "data", password="short") == 1
    assert "at least 8" in capsys.readouterr().err


def test_reset_password_unknown_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    signed_in(TestClient(make_app(tmp_path)))
    code = reset(monkeypatch, tmp_path / "data", "--username", "ghost", password=NEW_PASSWORD)
    assert code == 1
    assert "no account named 'ghost'" in capsys.readouterr().err


def test_reset_password_without_a_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert reset(monkeypatch, tmp_path / "empty", password=NEW_PASSWORD) == 1
    assert "no Athena database" in capsys.readouterr().err
    assert not (tmp_path / "empty").exists()


def test_reset_password_prompts_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    signed_in(TestClient(make_app(tmp_path)))
    answers = iter([NEW_PASSWORD, "something else"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    code = main(["admin", "reset-password", "--data-dir", str(tmp_path / "data")])
    assert code == 1
    assert "don't match" in capsys.readouterr().err
