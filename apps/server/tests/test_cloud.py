"""Cloud storage (/api/cloud): remotes, browsing, uploads and transfer jobs.

Most tests drive a real `rclone rcd` and skip where rclone isn't installed. Their
remotes are `alias` remotes over temporary folders, which the API normally hides
(they reach the host's disks), so those tests let them through.
"""

import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import signed_in
from fake_probe import FakeProbe
from fastapi.testclient import TestClient

from athena.cloud import remotes, transfers
from athena.cloud.rclone import Rclone, RcloneError
from athena.config import Settings
from athena.main import create_app
from athena.platform.detect import detect
from athena.platform.probe import RunResult
from athena.platform.store import CapabilityStore

RCLONE = shutil.which("rclone")
needs_rclone = pytest.mark.skipif(RCLONE is None, reason="rclone isn't installed")


def _store(ready: bool) -> CapabilityStore:
    probe = FakeProbe(os="darwin")
    if ready:
        probe.binaries["rclone"] = "/usr/bin/rclone"
        probe.commands[("/usr/bin/rclone", "version")] = RunResult(0, "rclone v1.76.0\n")
    return CapabilityStore(detector=lambda: detect(probe))


def _app(tmp_path: Path, rclone: Rclone | None = None, ready: bool = True):
    settings = Settings(data_dir=tmp_path / "data", web_dir=tmp_path / "no-web")
    return create_app(settings, capability_store=_store(ready), rclone=rclone)


def _wait(client: TestClient, job_id: str, timeout: float = 30) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job didn't finish")


@pytest.fixture
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transfers, "POLL_SECONDS", 0.05)


# --- Pure helpers ----------------------------------------------------------------------


def test_remote_paths_cant_leave_the_remote() -> None:
    assert remotes.check_path("/a/b/") == "a/b"
    assert remotes.fs_of("gd", "a/b") == "gd:a/b"
    for bad in ["..", "a/../b", "a//b", "./a", "a\\b"]:
        with pytest.raises(remotes.BadPath):
            remotes.check_path(bad)
    for bad in ["-x", " x", "x ", "a:b", "a/b", ""]:
        with pytest.raises(remotes.BadPath):
            remotes.check_remote_name(bad)
    remotes.check_remote_name("My Drive_2")


def test_providers_hide_local_backends_and_hidden_options() -> None:
    data = {
        "providers": [
            {"Name": "local", "Description": "Local Disk", "Options": []},
            {"Name": "alias", "Description": "Alias", "Options": []},
            {
                "Name": "webdav",
                "Description": "WebDAV",
                "Options": [
                    {"Name": "url", "Required": True, "Type": "string", "DefaultStr": ""},
                    {"Name": "pass", "IsPassword": True, "DefaultStr": ""},
                    {"Name": "secret_flag", "Hide": 1},
                    {
                        "Name": "vendor",
                        "Examples": [{"Value": "nextcloud", "Help": "Nextcloud"}],
                        "Default": False,
                    },
                ],
            },
        ]
    }
    [webdav] = remotes.parse_providers(data)
    assert webdav.name == "webdav"
    assert [o.name for o in webdav.options] == ["url", "pass", "vendor"]
    assert webdav.options[1].password
    assert webdav.options[2].examples[0].value == "nextcloud"


def test_progress_line() -> None:
    fraction, text = transfers.progress_of(
        {
            "bytes": 12_000_000,
            "totalBytes": 48_000_000,
            "speed": 2_000_000,
            "eta": 18,
            "transfers": 1,
            "totalTransfers": 3,
        }
    )
    assert fraction == 0.25
    assert text == "12.0 MB of 48.0 MB · 2.0 MB/s · 18 s left · 1 of 3 files"
    assert transfers.progress_of({})[0] is None


# --- Without rclone --------------------------------------------------------------------


def test_cloud_needs_the_capability(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path, ready=False)) as client:
        signed_in(client)
        res = client.get("/api/cloud/remotes")
        assert res.status_code == 503
        assert res.json()["detail"] == "rclone not found"


def test_cloud_needs_a_session(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        assert client.get("/api/cloud/remotes").status_code == 401


def test_rclone_missing_at_call_time(tmp_path: Path) -> None:
    rclone = Rclone(tmp_path / "data", binary=lambda: None)
    with TestClient(_app(tmp_path, rclone)) as client:
        signed_in(client)
        res = client.get("/api/cloud/remotes")
        assert res.status_code == 503
        assert "isn't installed" in res.json()["detail"]


class FakeRclone(Rclone):
    """Scripted answers per method; `job/status` stays unfinished until stopped."""

    def __init__(self, data_dir: Path) -> None:
        super().__init__(data_dir, binary=lambda: None)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.stopped = False

    async def call(self, method: str, params: dict[str, Any] | None = None, timeout=0) -> Any:
        params = params or {}
        self.calls.append((method, params))
        match method:
            case "config/dump":
                return {"box": {"type": "webdav"}}
            case "operations/stat":
                return {"item": {"Name": "big.bin", "Path": "big.bin", "Size": 10, "IsDir": False}}
            case "operations/copyfile":
                return {"jobid": 7}
            case "job/status":
                return {"finished": self.stopped, "success": False, "error": "context canceled"}
            case "core/stats":
                return {"bytes": 4, "totalBytes": 10}
            case "job/stop":
                self.stopped = True
                return {}
        return {}


def test_transfer_can_be_cancelled(tmp_path: Path, fast_poll: None) -> None:
    fake = FakeRclone(tmp_path / "data")
    with TestClient(_app(tmp_path, fake)) as client:
        signed_in(client)
        app_data = next(
            loc for loc in client.get("/api/files/locations").json() if loc["name"] == "App data"
        )
        Path(app_data["path"]).mkdir(parents=True, exist_ok=True)
        res = client.post(
            "/api/cloud/transfer",
            json={
                "op": "copy",
                "source": {"remote": "box"},
                "paths": ["big.bin"],
                "dest": {"location": app_data["id"]},
            },
        )
        assert res.status_code == 202, res.text
        job = res.json()
        assert job["cancellable"]
        deadline = time.monotonic() + 5
        while not any(m == "core/stats" for m, _ in fake.calls) and time.monotonic() < deadline:
            time.sleep(0.02)
        progress = client.get(f"/api/jobs/{job['id']}").json()["progress"]
        assert progress["fraction"] == 0.4
        assert client.post(f"/api/jobs/{job['id']}/cancel").status_code == 202
        done = _wait(client, job["id"])
        assert (done["status"], done["error"]) == ("failed", "Cancelled")
        assert ("job/stop", {"jobid": 7}) in fake.calls
        assert any(m == "core/stats-delete" for m, _ in fake.calls)
        # A finished job can't be cancelled.
        assert client.post(f"/api/jobs/{job['id']}/cancel").status_code == 409


def test_other_jobs_cant_be_cancelled(tmp_path: Path) -> None:
    with TestClient(_app(tmp_path)) as client:
        signed_in(client)
        jobs = client.app.state.jobs  # type: ignore[attr-defined]

        async def body(job: Any) -> None:
            import asyncio

            await asyncio.sleep(0.2)

        job = client.portal.call(jobs.start, "wait", body)  # type: ignore[union-attr]
        assert client.post(f"/api/jobs/{job.id}/cancel").status_code == 409
        _wait(client, job.id)


# --- With a real rclone ----------------------------------------------------------------


@pytest.fixture
def cloud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fast_poll: None):
    """A signed-in client, a location "Here" and an alias remote "box" (both folders)."""
    if RCLONE is None:
        pytest.skip("rclone isn't installed")
    monkeypatch.setattr(remotes, "HIDDEN_TYPES", {"local", "memory"})
    here = tmp_path / "here"
    box = tmp_path / "box"
    here.mkdir()
    box.mkdir()
    config = tmp_path / "data" / "rclone" / "rclone.conf"
    config.parent.mkdir(parents=True)
    config.write_bytes(f"[box]\ntype = alias\nremote = {box.as_posix()}\n".encode())
    with TestClient(_app(tmp_path)) as client:
        signed_in(client)
        res = client.post("/api/files/locations", json={"name": "Here", "path": str(here)})
        assert res.status_code == 201, res.text
        yield client, res.json()["id"], here, box


@needs_rclone
def test_providers_and_remote_lifecycle(cloud) -> None:
    client, _, _, _ = cloud
    providers = {p["name"]: p for p in client.get("/api/cloud/providers").json()}
    assert "drive" in providers and "s3" in providers
    assert "local" not in providers

    assert [r["name"] for r in client.get("/api/cloud/remotes").json()] == ["box"]
    res = client.post(
        "/api/cloud/remotes",
        json={
            "name": "dav",
            "type": "webdav",
            "parameters": {"url": "https://example.invalid/dav", "user": "me", "pass": "s3cret"},
        },
    )
    assert res.status_code == 201, res.text
    assert res.json() == {"remote": "dav", "done": True, "question": None, "error": ""}
    detail = client.get("/api/cloud/remotes/dav").json()
    assert detail["values"]["url"] == "https://example.invalid/dav"
    # Passwords and anything rclone calls sensitive (users, keys, tokens) stay hidden.
    assert {"pass", "user"} <= set(detail["secrets"])
    assert "pass" not in detail["values"]
    assert "s3cret" not in client.get("/api/cloud/remotes/dav").text

    # Editing with the password left empty keeps it.
    obscured = client.app.state.rclone.call_sync("config/get", {"name": "dav"})["pass"]  # type: ignore[attr-defined]
    res = client.put("/api/cloud/remotes/dav", json={"parameters": {"user": "you", "pass": ""}})
    assert res.status_code == 200, res.text
    dump = client.app.state.rclone.call_sync("config/get", {"name": "dav"})  # type: ignore[attr-defined]
    assert (dump["user"], dump["pass"]) == ("you", obscured)

    assert (
        client.post(
            "/api/cloud/remotes", json={"name": "dav", "type": "webdav", "parameters": {}}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/cloud/remotes", json={"name": "x", "type": "local", "parameters": {}}
        ).status_code
        == 400
    )
    assert client.delete("/api/cloud/remotes/dav").status_code == 204
    assert client.get("/api/cloud/remotes/dav").status_code == 404
    actions = [a for a in _audit(client) if a.startswith("cloud.remote")]
    assert actions == ["cloud.remote.create", "cloud.remote.edit", "cloud.remote.remove"]


def _audit(client: TestClient) -> list[str]:
    from sqlmodel import select

    from athena.db.models import AuditEntry

    for db in client.app.state.db.session():  # type: ignore[attr-defined]
        return [e.action for e in db.exec(select(AuditEntry))]
    return []


@needs_rclone
def test_oauth_remote_asks_for_a_token_from_rclone_authorize(cloud) -> None:
    client, _, _, _ = cloud
    step = client.post(
        "/api/cloud/remotes", json={"name": "gd", "type": "drive", "parameters": {}}
    ).json()
    # Newer rclone first warns about Google's shared client id; say yes to anything
    # else until it asks for the token (Athena answers "browser on this machine?").
    for _ in range(5):
        question = step["question"]
        assert question is not None
        if question["option"]["name"] == "config_token":
            break
        step = client.post(
            "/api/cloud/remotes/gd/answer",
            json={"state": question["state"], "answer": question["option"]["default"] or "true"},
        ).json()
    assert step["question"]["option"]["name"] == "config_token"
    assert 'rclone authorize "drive"' in step["question"]["option"]["help"]
    # A bad paste is refused; the same question is asked again.
    res = client.post(
        "/api/cloud/remotes/gd/answer",
        json={"state": step["question"]["state"], "answer": "not a token"},
    )
    assert res.status_code == 200, res.text
    refused = res.json()
    assert (refused["done"], refused["question"]) == (False, None)
    assert "decode" in refused["error"]
    assert client.delete("/api/cloud/remotes/gd").status_code == 204


@needs_rclone
def test_browse_and_change_a_remote(cloud) -> None:
    client, _, _, box = cloud
    (box / "docs").mkdir()
    (box / "docs" / "a.txt").write_bytes(b"hello")
    (box / ".hidden").write_bytes(b"")

    listing = client.get("/api/cloud/files/list", params={"remote": "box"}).json()
    assert [(e["name"], e["kind"], e["hidden"]) for e in listing["entries"]] == [
        ("docs", "dir", False),
        (".hidden", "file", True),
    ]
    inner = client.get("/api/cloud/files/list", params={"remote": "box", "path": "docs"}).json()
    assert inner["entries"][0] | {"modified": None} == {
        "name": "a.txt",
        "path": "docs/a.txt",
        "kind": "file",
        "size": 5,
        "modified": None,
        "is_link": False,
        "hidden": False,
    }
    for bad in ["..", "docs/../.."]:
        res = client.get("/api/cloud/files/list", params={"remote": "box", "path": bad})
        assert res.status_code == 400
    assert client.get("/api/cloud/files/list", params={"remote": "nope"}).status_code == 404
    res = client.get("/api/cloud/files/list", params={"remote": "box", "path": "missing"})
    assert res.status_code == 404

    res = client.get("/api/cloud/files/download", params={"remote": "box", "path": "docs/a.txt"})
    assert res.status_code == 200 and res.content == b"hello"
    assert res.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in res.headers["content-security-policy"]
    res = client.get("/api/cloud/files/download", params={"remote": "box", "path": "docs"})
    assert res.status_code == 400

    res = client.post(
        "/api/cloud/files/folder", json={"remote": "box", "path": "docs", "name": "new"}
    )
    assert res.status_code == 201 and (box / "docs" / "new").is_dir()
    res = client.post(
        "/api/cloud/files/folder", json={"remote": "box", "path": "docs", "name": "new"}
    )
    assert res.status_code == 409
    res = client.post("/api/cloud/files/folder", json={"remote": "box", "name": "a:b"})
    assert res.status_code == 400

    res = client.post(
        "/api/cloud/files/rename", json={"remote": "box", "path": "docs/a.txt", "name": "b.txt"}
    )
    assert res.status_code == 200, res.text
    assert res.json()["path"] == "docs/b.txt"
    assert (box / "docs" / "b.txt").read_bytes() == b"hello"
    res = client.post(
        "/api/cloud/files/rename", json={"remote": "box", "path": "docs", "name": "papers"}
    )
    assert res.status_code == 200, res.text
    assert (box / "papers" / "b.txt").is_file() and not (box / "docs").exists()
    assert (box / "papers" / "new").is_dir()

    res = client.post(
        "/api/cloud/files/delete", json={"remote": "box", "paths": ["papers", "gone"]}
    )
    body = res.json()
    assert body["deleted"] == ["papers"] and body["errors"][0]["path"] == "gone"
    assert not (box / "papers").exists()
    assert "cloud.delete" in _audit(client)


@needs_rclone
def test_upload_to_a_remote_in_pieces(cloud) -> None:
    client, _, _, box = cloud
    data = bytes(range(256)) * 100
    common = {
        "remote": "box",
        "path": "",
        "name": "up.bin",
        "upload_id": "abcdefgh12",
        "total": len(data),
    }
    binary = {"Content-Type": "application/octet-stream"}
    res = client.post(
        "/api/cloud/files/upload",
        params={**common, "offset": 0},
        content=data[:10000],
        headers=binary,
    )
    assert res.json() == {"received": 10000, "entry": None}
    res = client.post(
        "/api/cloud/files/upload",
        params={**common, "offset": 10000},
        content=data[10000:],
        headers=binary,
    )
    assert res.status_code == 200, res.text
    assert res.json()["entry"]["size"] == len(data)
    assert (box / "up.bin").read_bytes() == data
    assert not any((client.app.state.rclone.dir / "uploads").iterdir())  # type: ignore[attr-defined]

    res = client.post(
        "/api/cloud/files/upload", params={**common, "offset": 0}, content=b"x", headers=binary
    )
    assert res.status_code == 409
    res = client.post(
        "/api/cloud/files/upload",
        params={**common, "offset": 0, "total": 1, "overwrite": True},
        content=b"x",
        headers=binary,
    )
    assert res.status_code == 200 and (box / "up.bin").read_bytes() == b"x"


@needs_rclone
def test_copy_and_move_between_a_location_and_a_remote(cloud) -> None:
    client, here_id, here, box = cloud
    (here / "photos").mkdir()
    (here / "photos" / "1.jpg").write_bytes(b"one")
    (here / "photos" / "empty").mkdir()
    (here / "note.txt").write_bytes(b"note")

    res = client.post(
        "/api/cloud/transfer",
        json={
            "op": "copy",
            "source": {"location": here_id},
            "paths": ["photos", "note.txt"],
            "dest": {"remote": "box", "path": ""},
        },
    )
    assert res.status_code == 202, res.text
    job = _wait(client, res.json()["id"])
    assert job["status"] == "succeeded", job
    assert (box / "photos" / "1.jpg").read_bytes() == b"one"
    assert (box / "photos" / "empty").is_dir()
    assert (box / "note.txt").read_bytes() == b"note"
    assert (here / "note.txt").exists()
    assert job["progress"]["fraction"] == 1.0

    (here / "back").mkdir()
    res = client.post(
        "/api/cloud/transfer",
        json={
            "op": "move",
            "source": {"remote": "box"},
            "paths": ["photos", "note.txt"],
            "dest": {"location": here_id, "path": "back"},
        },
    )
    job = _wait(client, res.json()["id"])
    assert job["status"] == "succeeded", job
    assert (here / "back" / "photos" / "1.jpg").read_bytes() == b"one"
    assert (here / "back" / "note.txt").read_bytes() == b"note"
    assert not (box / "note.txt").exists()
    assert not (box / "photos" / "1.jpg").exists()

    # Location to location stays with the file manager; folders can't go into themselves.
    res = client.post(
        "/api/cloud/transfer",
        json={
            "op": "copy",
            "source": {"location": here_id},
            "paths": ["back"],
            "dest": {"location": here_id},
        },
    )
    assert res.status_code == 400
    (box / "d").mkdir()
    res = client.post(
        "/api/cloud/transfer",
        json={
            "op": "copy",
            "source": {"remote": "box"},
            "paths": ["d"],
            "dest": {"remote": "box", "path": "d"},
        },
    )
    assert res.status_code == 400
    res = client.post(
        "/api/cloud/transfer",
        json={
            "op": "copy",
            "source": {"location": here_id},
            "paths": ["../x"],
            "dest": {"remote": "box"},
        },
    )
    assert res.status_code == 400
    assert {"cloud.copy", "cloud.move"} <= set(_audit(client))


@needs_rclone
def test_sync_previews_then_mirrors(cloud) -> None:
    client, here_id, here, box = cloud
    (here / "src").mkdir()
    (here / "src" / "keep.txt").write_bytes(b"keep")
    (here / "src" / "new.txt").write_bytes(b"new")
    (box / "mirror").mkdir()
    (box / "mirror" / "keep.txt").write_bytes(b"keep")
    (box / "mirror" / "old.txt").write_bytes(b"old")
    body = {
        "source": {"location": here_id, "path": "src"},
        "dest": {"remote": "box", "path": "mirror"},
    }

    preview = client.post("/api/cloud/sync/preview", json=body).json()
    assert preview == {"copy_count": 1, "delete_count": 1, "deletes": ["old.txt"]}
    fresh = client.post(
        "/api/cloud/sync/preview", json={**body, "dest": {"remote": "box", "path": "fresh"}}
    ).json()
    assert fresh == {"copy_count": 2, "delete_count": 0, "deletes": []}

    job = _wait(client, client.post("/api/cloud/sync", json=body).json()["id"])
    assert job["status"] == "succeeded", job
    assert sorted(p.name for p in (box / "mirror").iterdir()) == ["keep.txt", "new.txt"]
    assert "cloud.sync" in _audit(client)

    res = client.post(
        "/api/cloud/sync",
        json={"source": {"remote": "box"}, "dest": {"remote": "box", "path": "mirror"}},
    )
    assert res.status_code == 400


@needs_rclone
def test_failed_transfer_reports_the_error(cloud) -> None:
    client, here_id, here, _ = cloud
    (here / "f.txt").write_bytes(b"x")
    rclone: Rclone = client.app.state.rclone  # type: ignore[attr-defined]
    rclone.call_sync(
        "config/create",
        {
            "name": "broken",
            "type": "webdav",
            "parameters": {"url": "http://127.0.0.1:9/"},
            "opt": {"nonInteractive": True},
        },
    )
    res = client.post(
        "/api/cloud/transfer",
        json={
            "op": "copy",
            "source": {"location": here_id},
            "paths": ["f.txt"],
            "dest": {"remote": "broken"},
        },
    )
    job = _wait(client, res.json()["id"])
    assert job["status"] == "failed"
    assert job["error"] == "The transfer failed"
    assert any("failed:" in line for line in job["lines"])


@needs_rclone
def test_rclone_restarts_after_it_dies(tmp_path: Path) -> None:
    rclone = Rclone(tmp_path)
    try:
        assert rclone.call_sync("core/version")["version"].startswith("v")
        assert rclone._proc is not None
        rclone._proc.kill()
        rclone._proc.wait()
        assert rclone.call_sync("core/version")["version"].startswith("v")
        with pytest.raises(RcloneError) as err:
            rclone.call_sync("operations/list", {"fs": "nosuch:", "remote": ""})
        assert "nosuch" in err.value.message
    finally:
        rclone.stop()
    assert rclone._proc is None
