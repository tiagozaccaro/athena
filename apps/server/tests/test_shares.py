import io
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import make_app, signed_in
from fastapi.testclient import TestClient
from sqlmodel import select
from test_files import audit_actions, symlink

from athena.db.models import Share


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "share"
    (root / "photos" / "2024").mkdir(parents=True)
    (root / "photos" / "a.jpg").write_bytes(b"jpeg a")
    (root / "photos" / "2024" / "b.png").write_bytes(b"png b")
    (root / "secret.txt").write_text("not shared")
    (root / "inbox").mkdir()
    return root


@pytest.fixture
def admin(tmp_path: Path, tree: Path) -> Iterator[tuple[TestClient, int]]:
    with TestClient(make_app(tmp_path)) as client:
        signed_in(client)
        res = client.post("/api/files/locations", json={"name": "Share", "path": str(tree)})
        assert res.status_code == 201, res.text
        yield client, res.json()["id"]


@pytest.fixture
def visitor(admin: tuple[TestClient, int]) -> Iterator[TestClient]:
    """Someone with the link and no Athena account."""
    client, _ = admin
    # Not as a context manager: the app (and its lifespan) is already running.
    yield TestClient(client.app)


def share(client: TestClient, location: int, path: str, **body) -> dict:
    res = client.post("/api/shares", json={"location": location, "path": path, **body})
    assert res.status_code == 201, res.text
    return res.json()


def base(link: dict) -> str:
    return f"/api/public/shares/{link['token']}"


def test_read_link_to_a_folder(admin, visitor) -> None:
    client, loc = admin
    link = share(client, loc, "photos")
    assert link["url_path"] == f"/s/{link['token']}"
    assert (link["name"], link["kind"], link["mode"]) == ("photos", "dir", "read")
    assert not link["has_password"] and link["expires_at"] is None

    info = visitor.get(base(link)).json()
    assert info["locked"] is False and info["name"] == "photos" and info["kind"] == "dir"
    names = [e["name"] for e in visitor.get(f"{base(link)}/list").json()["entries"]]
    assert names == ["2024", "a.jpg"]
    sub = visitor.get(f"{base(link)}/list", params={"path": "2024"}).json()
    assert [e["path"] for e in sub["entries"]] == ["2024/b.png"]

    res = visitor.get(f"{base(link)}/download", params={"path": "2024/b.png"})
    assert res.content == b"png b"
    assert res.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in res.headers["content-security-policy"]
    res = visitor.get(f"{base(link)}/download")
    names = zipfile.ZipFile(io.BytesIO(res.content)).namelist()
    assert sorted(names) == ["photos/2024/b.png", "photos/a.jpg"]
    preview = visitor.get(f"{base(link)}/download", params={"path": "a.jpg", "inline": True})
    assert preview.headers["content-disposition"].startswith("inline")

    counted = client.get("/api/shares").json()[0]
    assert counted["downloads"] == 2  # previews don't count


def test_a_link_stays_inside_what_it_shares(admin, visitor, tree: Path) -> None:
    client, loc = admin
    link = share(client, loc, "photos")
    for bad in ["..", "../secret.txt", "2024/../../secret.txt"]:
        res = visitor.get(f"{base(link)}/download", params={"path": bad})
        assert res.status_code in (400, 403), bad
    # A link inside the shared folder to elsewhere in the same location is refused too.
    symlink(tree / "photos" / "escape.txt", tree / "secret.txt")
    res = visitor.get(f"{base(link)}/download", params={"path": "escape.txt"})
    assert res.status_code == 403


def test_read_link_to_a_file(admin, visitor) -> None:
    client, loc = admin
    link = share(client, loc, "photos/a.jpg")
    info = visitor.get(base(link)).json()
    assert (info["name"], info["kind"], info["size"]) == ("a.jpg", "file", 6)
    assert visitor.get(f"{base(link)}/download").content == b"jpeg a"
    assert visitor.get(f"{base(link)}/list").status_code == 400
    res = visitor.get(f"{base(link)}/download", params={"path": "../secret.txt"})
    assert res.status_code == 400


def test_password(admin, visitor) -> None:
    client, loc = admin
    link = share(client, loc, "photos", password="open sesame")
    assert link["has_password"]
    info = visitor.get(base(link)).json()
    assert info == {
        "mode": "read",
        "locked": True,
        "name": None,
        "kind": None,
        "size": None,
        "modified": None,
        "expires_at": None,
    }
    assert visitor.get(f"{base(link)}/list").status_code == 403
    assert visitor.post(f"{base(link)}/unlock", json={"password": "nope"}).status_code == 403
    assert visitor.post(f"{base(link)}/unlock", json={"password": "open sesame"}).status_code == 204
    assert visitor.get(base(link)).json()["locked"] is False
    assert visitor.get(f"{base(link)}/list").status_code == 200

    # A new password signs out whoever unlocked it.
    res = client.put(f"/api/shares/{link['id']}", json={"mode": "read", "password": "another"})
    assert res.status_code == 200
    assert visitor.get(f"{base(link)}/list").status_code == 403
    res = client.put(f"/api/shares/{link['id']}", json={"mode": "read", "remove_password": True})
    assert res.json()["has_password"] is False
    assert visitor.get(f"{base(link)}/list").status_code == 200


def test_wrong_passwords_are_throttled(admin, visitor) -> None:
    client, loc = admin
    link = share(client, loc, "photos", password="right")
    for _ in range(10):
        assert visitor.post(f"{base(link)}/unlock", json={"password": "x"}).status_code == 403
    res = visitor.post(f"{base(link)}/unlock", json={"password": "right"})
    assert res.status_code == 429 and "Retry-After" in res.headers


def test_expiry(admin, visitor) -> None:
    client, loc = admin
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    res = client.post("/api/shares", json={"location": loc, "path": "photos", "expires_at": past})
    assert res.status_code == 400
    soon = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    link = share(client, loc, "photos", expires_at=soon)
    assert link["expires_at"] and not link["expired"]
    assert visitor.get(base(link)).status_code == 200

    with next(client.app.state.db.session()) as db:  # type: ignore[attr-defined]
        row = db.exec(select(Share)).one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.add(row)
        db.commit()
    assert visitor.get(base(link)).status_code == 410
    assert visitor.get(f"{base(link)}/download").status_code == 410
    assert client.get("/api/shares").json()[0]["expired"] is True


def test_upload_link(admin, visitor, tree: Path) -> None:
    client, loc = admin
    res = client.post("/api/shares", json={"location": loc, "path": "secret.txt", "mode": "upload"})
    assert res.status_code == 400  # needs a folder
    link = share(client, loc, "inbox", mode="upload")
    info = visitor.get(base(link)).json()
    assert info["mode"] == "upload" and info["kind"] == "dir"
    assert visitor.get(f"{base(link)}/list").status_code == 403
    assert visitor.get(f"{base(link)}/download").status_code == 403

    def upload(name: str, data: bytes, upload_id: str) -> dict:
        res = visitor.post(
            f"{base(link)}/upload",
            params={"name": name, "upload_id": upload_id, "offset": 0, "total": len(data)},
            content=data,
        )
        assert res.status_code == 200, res.text
        return res.json()

    first = upload("report.pdf", b"one", "upload-0001")
    assert first["entry"]["name"] == "report.pdf"
    # The same name never replaces what's there.
    second = upload("report.pdf", b"two", "upload-0002")
    assert second["entry"]["name"] == "report (1).pdf"
    assert (tree / "inbox" / "report.pdf").read_bytes() == b"one"
    assert (tree / "inbox" / "report (1).pdf").read_bytes() == b"two"
    bad = visitor.post(
        f"{base(link)}/upload",
        params={"name": "../x", "upload_id": "upload-0003", "offset": 0, "total": 1},
        content=b"x",
    )
    assert bad.status_code == 400

    assert client.get("/api/shares").json()[0]["uploads"] == 2
    uploads = [a for a in audit_actions(client) if a[0] == "share.upload"]
    assert uploads[0][0:2] == ("share.upload", "Share:/inbox")
    # A read link doesn't take uploads.
    read = share(client, loc, "photos")
    res = visitor.post(
        f"{base(read)}/upload",
        params={"name": "x", "upload_id": "upload-0004", "offset": 0, "total": 1},
        content=b"x",
    )
    assert res.status_code == 403


def test_managing_links(admin, visitor) -> None:
    client, loc = admin
    a = share(client, loc, "photos")
    b = share(client, loc, "")
    assert b["name"] == "Share"
    assert [s["id"] for s in client.get("/api/shares").json()] == [b["id"], a["id"]]
    only = client.get("/api/shares", params={"location": loc, "path": "photos"}).json()
    assert [s["id"] for s in only] == [a["id"]]
    res = client.put(f"/api/shares/{a['id']}", json={"mode": "upload"})
    assert res.json()["mode"] == "upload"

    assert client.delete(f"/api/shares/{a['id']}").status_code == 204
    assert visitor.get(base(a)).status_code == 404
    assert client.delete(f"/api/shares/{a['id']}").status_code == 404
    # Forgetting the location removes its links.
    assert client.delete(f"/api/files/locations/{loc}").status_code == 204
    assert client.get("/api/shares").json() == []
    assert visitor.get(base(b)).status_code == 404

    actions = [a[0] for a in audit_actions(client) if a[0].startswith("share.")]
    assert actions == ["share.create", "share.create", "share.edit", "share.remove"]


def test_a_missing_item_or_bad_token(admin, visitor, tree: Path) -> None:
    client, loc = admin
    link = share(client, loc, "photos/a.jpg")
    (tree / "photos" / "a.jpg").unlink()
    assert client.get("/api/shares").json()[0]["kind"] is None
    assert visitor.get(base(link)).status_code == 404
    assert visitor.get("/api/public/shares/not-a-real-token-at-all").status_code == 404
    res = client.post("/api/shares", json={"location": loc, "path": "nope"})
    assert res.status_code == 404


def test_managing_needs_a_session(admin, visitor) -> None:
    assert visitor.get("/api/shares").status_code == 401


def test_share_page_is_served_for_any_token(tmp_path: Path) -> None:
    web = tmp_path / "web"
    (web / "s").mkdir(parents=True)
    (web / "index.html").write_text("home")
    (web / "s" / "index.html").write_text("share page")
    with TestClient(make_app(tmp_path, web_dir=web)) as client:
        res = client.get("/s/abc123")
        assert res.text == "share page"
        assert res.headers["referrer-policy"] == "no-referrer"
        assert client.get("/s/abc123/").text == "share page"
