import io
import os
import sys
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import make_app, signed_in
from fastapi.testclient import TestClient
from sqlmodel import select

from athena.db.models import AuditEntry
from athena.files import ops
from athena.files.paths import BadPath, available_name, check_new_name, split


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "share"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "notes.txt").write_text("hello\n")
    (root / "photo.png").write_bytes(b"\x89PNG fake")
    (root / "page.html").write_text("<script>alert(1)</script>")
    (root / ".hidden").write_text("x")
    (root / "Zeta").mkdir()
    return root


@pytest.fixture
def api(tmp_path: Path, tree: Path) -> Iterator[tuple[TestClient, int]]:
    with TestClient(make_app(tmp_path)) as client:
        signed_in(client)
        res = client.post("/api/files/locations", json={"name": "Share", "path": str(tree)})
        assert res.status_code == 201, res.text
        yield client, res.json()["id"]


def symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError:
        pytest.skip("can't create symlinks here (Windows without Developer Mode)")


def wait(client: TestClient, job_id: str) -> dict:
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job didn't finish")


def audit_actions(client: TestClient) -> list[tuple[str, str | None, str | None]]:
    with next(client.app.state.db.session()) as db:  # type: ignore[attr-defined]
        rows = db.exec(select(AuditEntry).order_by(AuditEntry.id)).all()  # type: ignore[arg-type]
        return [(r.action, r.target, r.detail) for r in rows]


# --- Paths -----------------------------------------------------------------------------


def test_split_refuses_traversal() -> None:
    assert split("") == []
    assert split("/a/b/") == ["a", "b"]
    for bad in ["..", "a/../b", "a//b", "./a", "a\0b"]:
        with pytest.raises(BadPath):
            split(bad)


def test_new_names_are_portable() -> None:
    assert check_new_name("Holiday 2024.jpg") == "Holiday 2024.jpg"
    for bad in [
        "",
        ".",
        "..",
        "a/b",
        "a\\b",
        "a:b",
        "what?",
        "trailing.",
        " lead",
        "CON",
        "con.txt",
        ".athena-upload-x",
        "x" * 256,
    ]:
        with pytest.raises(BadPath):
            check_new_name(bad)


def test_available_name(tmp_path: Path) -> None:
    (tmp_path / "a.tar.gz").write_text("")
    (tmp_path / "a.tar (1).gz").write_text("")
    (tmp_path / ".bashrc").write_text("")
    (tmp_path / "dir").mkdir()
    assert available_name(tmp_path, "new.txt") == "new.txt"
    assert available_name(tmp_path, "a.tar.gz") == "a.tar (2).gz"
    assert available_name(tmp_path, ".bashrc") == ".bashrc (1)"
    assert available_name(tmp_path, "dir") == "dir (1)"


# --- Locations -------------------------------------------------------------------------


def test_files_need_a_session(tmp_path: Path) -> None:
    client = TestClient(make_app(tmp_path))
    assert client.get("/api/files/locations").status_code == 401
    assert client.get("/api/files/list", params={"location": 1}).status_code == 401


def test_default_locations_are_seeded_once(tmp_path: Path) -> None:
    client = signed_in(TestClient(make_app(tmp_path)))
    found = {loc["name"]: loc for loc in client.get("/api/files/locations").json()}
    assert found["App data"]["path"] == str((tmp_path / "data" / "apps").resolve())
    assert found["App data"]["available"] and found["App data"]["writable"]
    for loc in found.values():
        assert client.delete(f"/api/files/locations/{loc['id']}").status_code == 204
    # A restart doesn't bring removed defaults back.
    again = TestClient(make_app(tmp_path))
    again.headers.update(client.headers)
    again.cookies = client.cookies
    assert again.get("/api/files/locations").json() == []


def test_location_validation(api: tuple[TestClient, int], tree: Path) -> None:
    client, loc = api
    res = client.post("/api/files/locations", json={"name": "Rel", "path": "relative/dir"})
    assert res.status_code == 400 and "absolute" in res.json()["detail"]
    res = client.post("/api/files/locations", json={"name": "Gone", "path": str(tree / "nope")})
    assert res.status_code == 400
    res = client.post("/api/files/locations", json={"name": "Share", "path": str(tree / "docs")})
    assert res.status_code == 409
    res = client.put(
        f"/api/files/locations/{loc}", json={"name": "Docs", "path": str(tree / "docs")}
    )
    assert res.status_code == 200 and res.json()["name"] == "Docs"
    listed = client.get("/api/files/list", params={"location": loc}).json()
    assert [e["name"] for e in listed["entries"]] == ["notes.txt"]
    actions = [a for a, _, _ in audit_actions(client)]
    assert actions[-2:] == ["files.location.add", "files.location.edit"]


def test_missing_location_folder(api: tuple[TestClient, int], tmp_path: Path) -> None:
    client, _ = api
    gone = tmp_path / "gone"
    gone.mkdir()
    loc = client.post("/api/files/locations", json={"name": "Gone", "path": str(gone)}).json()
    gone.rmdir()
    assert client.get("/api/files/locations").json()[-1]["available"] is False
    res = client.get("/api/files/list", params={"location": loc["id"]})
    assert res.status_code == 404
    assert client.get("/api/files/list", params={"location": 999}).status_code == 404


# --- Reading ---------------------------------------------------------------------------


def test_list_sorts_folders_first_and_marks_hidden(api: tuple[TestClient, int], tree: Path) -> None:
    client, loc = api
    ops.upload_part(tree, "abcdefgh").write_bytes(b"partial")
    res = client.get("/api/files/list", params={"location": loc})
    assert res.status_code == 200
    body = res.json()
    assert body["path"] == ""
    names = [e["name"] for e in body["entries"]]
    assert names == ["docs", "Zeta", ".hidden", "page.html", "photo.png"]
    by_name = {e["name"]: e for e in body["entries"]}
    assert by_name["docs"]["kind"] == "dir" and by_name["docs"]["size"] is None
    assert by_name["photo.png"] == {
        **by_name["photo.png"],
        "kind": "file",
        "size": 9,
        "path": "photo.png",
        "hidden": False,
    }
    assert by_name[".hidden"]["hidden"] is True
    sub = client.get("/api/files/list", params={"location": loc, "path": "docs"}).json()
    assert sub["entries"][0]["path"] == "docs/notes.txt"


def test_list_errors(api: tuple[TestClient, int]) -> None:
    client, loc = api
    get = lambda p: client.get("/api/files/list", params={"location": loc, "path": p})  # noqa: E731
    assert get("../..").status_code == 400
    assert get("nope").status_code == 404
    assert get("photo.png").status_code == 400


def test_links_out_of_a_location_are_refused(
    api: tuple[TestClient, int], tree: Path, tmp_path: Path
) -> None:
    client, loc = api
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "key.txt").write_text("private")
    symlink(tree / "escape", secret)
    symlink(tree / "notes-link.txt", tree / "docs" / "notes.txt")
    by_name = {
        e["name"]: e
        for e in client.get("/api/files/list", params={"location": loc}).json()["entries"]
    }
    assert by_name["escape"]["is_link"] and by_name["escape"]["kind"] == "dir"
    for path in ["escape", "escape/key.txt"]:
        assert (
            client.get("/api/files/list", params={"location": loc, "path": path}).status_code == 403
        )
        params = {"location": loc, "path": path}
        assert client.get("/api/files/download", params=params).status_code == 403
        assert client.get("/api/files/text", params=params).status_code == 403
    # A link inside the location works.
    res = client.get("/api/files/text", params={"location": loc, "path": "notes-link.txt"})
    assert res.json()["content"] == "hello\n"
    # The zip leaves the outside link out.
    res = client.get("/api/files/download", params={"location": loc})
    names = zipfile.ZipFile(io.BytesIO(res.content)).namelist()
    assert "Share/notes-link.txt" in names
    assert not any("key.txt" in n for n in names)
    # Deleting the link removes the link, not what it points to.
    res = client.post(
        "/api/files/delete", json={"location": loc, "paths": ["escape"], "permanent": True}
    )
    assert res.json() == {"deleted": ["escape"], "errors": []}
    assert not (tree / "escape").exists(follow_symlinks=False)
    assert (secret / "key.txt").read_text() == "private"


def test_text_read_and_write(api: tuple[TestClient, int], tree: Path) -> None:
    client, loc = api
    params = {"location": loc, "path": "docs/notes.txt"}
    read = client.get("/api/files/text", params=params).json()
    assert read["content"] == "hello\n"
    res = client.put(
        "/api/files/text",
        json={**params, "content": "changed\r\n", "version": read["version"]},
    )
    assert res.status_code == 200, res.text
    assert (tree / "docs" / "notes.txt").read_bytes() == b"changed\r\n"
    # Saving with the old version again is refused: the file changed since that read.
    time.sleep(0.01)
    res = client.put(
        "/api/files/text", json={**params, "content": "lost", "version": read["version"]}
    )
    assert res.status_code == 409
    (tree / "bin").write_bytes(b"\0\1\2")
    assert client.get("/api/files/text", params={"location": loc, "path": "bin"}).status_code == 400
    (tree / "latin1").write_bytes("café".encode("latin-1"))
    res = client.get("/api/files/text", params={"location": loc, "path": "latin1"})
    assert res.status_code == 400 and "UTF-8" in res.json()["detail"]


def test_downloads_never_render_as_the_app(api: tuple[TestClient, int]) -> None:
    client, loc = api
    res = client.get(
        "/api/files/download", params={"location": loc, "path": "page.html", "inline": True}
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert res.headers["content-disposition"].startswith("attachment;")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in res.headers["content-security-policy"]
    res = client.get(
        "/api/files/download", params={"location": loc, "path": "photo.png", "inline": True}
    )
    assert res.headers["content-type"] == "image/png"
    assert res.headers["content-disposition"].startswith("inline;")
    res = client.get("/api/files/download", params={"location": loc, "path": "photo.png"})
    assert res.headers["content-disposition"].startswith("attachment;")
    assert res.content == b"\x89PNG fake"


def test_folder_downloads_as_zip(api: tuple[TestClient, int], tree: Path) -> None:
    client, loc = api
    (tree / "docs" / "empty").mkdir()
    (tree / "docs" / "ünïcode.txt").write_text("ü")
    res = client.get("/api/files/download", params={"location": loc, "path": "docs"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "filename*=UTF-8''docs.zip" in res.headers["content-disposition"]
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    assert sorted(zf.namelist()) == ["docs/empty/", "docs/notes.txt", "docs/ünïcode.txt"]
    assert zf.read("docs/notes.txt") == b"hello\n"


# --- Changing --------------------------------------------------------------------------


def test_create_folder_and_rename(api: tuple[TestClient, int], tree: Path) -> None:
    client, loc = api
    res = client.post("/api/files/folder", json={"location": loc, "path": "docs", "name": "New"})
    assert res.status_code == 201 and res.json()["path"] == "docs/New"
    assert (tree / "docs" / "New").is_dir()
    res = client.post("/api/files/folder", json={"location": loc, "path": "docs", "name": "New"})
    assert res.status_code == 409
    res = client.post("/api/files/folder", json={"location": loc, "name": "a:b"})
    assert res.status_code == 400
    res = client.post(
        "/api/files/rename", json={"location": loc, "path": "docs/New", "name": "Old"}
    )
    assert res.json()["path"] == "docs/Old"
    res = client.post(
        "/api/files/rename", json={"location": loc, "path": "docs/Old", "name": "notes.txt"}
    )
    assert res.status_code == 409
    res = client.post(
        "/api/files/rename", json={"location": loc, "path": "docs/Old", "name": "OLD"}
    )
    assert res.status_code == 200 and res.json()["name"] == "OLD"
    res = client.post("/api/files/rename", json={"location": loc, "path": "", "name": "x"})
    assert res.status_code == 422  # path is required


def test_delete_to_trash_or_permanently(
    api: tuple[TestClient, int], tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, loc = api
    trashed: list[Path] = []
    monkeypatch.setattr(ops, "send2trash", trashed.append)
    res = client.post("/api/files/delete", json={"location": loc, "paths": ["photo.png", "nope"]})
    assert res.json() == {
        "deleted": ["photo.png"],
        "errors": [{"path": "nope", "error": "Not found: nope"}],
    }
    assert trashed == [tree / "photo.png"]
    res = client.post(
        "/api/files/delete", json={"location": loc, "paths": ["docs"], "permanent": True}
    )
    assert res.json()["deleted"] == ["docs"]
    assert not (tree / "docs").exists()
    assert audit_actions(client)[-1] == ("file.delete", "Share:/", "permanently: docs")
    res = client.post("/api/files/delete", json={"location": loc, "paths": [""]})
    assert res.status_code == 422


def test_copy_and_move(api: tuple[TestClient, int], tree: Path, tmp_path: Path) -> None:
    client, loc = api
    other = tmp_path / "other"
    other.mkdir()
    dest = client.post("/api/files/locations", json={"name": "Other", "path": str(other)}).json()

    def run(**body) -> dict:
        res = client.post("/api/files/transfer", json={"location": loc, **body})
        assert res.status_code == 202, res.text
        return wait(client, res.json()["id"])

    # Copy into the same folder gets a new name.
    job = run(op="copy", paths=["docs"], dest_location=loc)
    assert job["status"] == "succeeded", job
    assert (tree / "docs (1)" / "notes.txt").read_text() == "hello\n"
    # Skip leaves the existing one.
    job = run(op="copy", paths=["docs"], dest_location=loc, on_conflict="skip")
    assert "skipped" in job["lines"][0] and not (tree / "docs (2)").exists()
    # Overwrite replaces files, never folders.
    (other / "photo.png").write_text("old")
    job = run(
        op="copy", paths=["photo.png", "docs"], dest_location=dest["id"], on_conflict="overwrite"
    )
    assert job["status"] == "succeeded"
    assert (other / "photo.png").read_bytes() == b"\x89PNG fake"
    job = run(op="copy", paths=["docs"], dest_location=dest["id"], on_conflict="overwrite")
    assert job["status"] == "failed" and "isn't replaced" in job["lines"][0]
    # Move to another location.
    job = run(op="move", paths=["Zeta", "page.html"], dest_location=dest["id"])
    assert job["status"] == "succeeded"
    assert (other / "Zeta").is_dir() and not (tree / "Zeta").exists()
    assert audit_actions(client)[-1][0] == "file.move"
    # Not into itself.
    job = run(op="move", paths=["docs"], dest_location=loc, dest_path="docs")
    assert job["status"] == "failed" and "into itself" in job["lines"][0]
    res = client.post(
        "/api/files/transfer",
        json={
            "op": "copy",
            "location": loc,
            "paths": ["docs"],
            "dest_location": loc,
            "dest_path": "photo.png",
        },
    )
    assert res.status_code == 400


# --- Uploads ---------------------------------------------------------------------------


def upload(client: TestClient, loc: int, name: str, data: bytes, chunk: int = 4, **extra) -> list:
    answers = []
    for offset in range(0, max(len(data), 1), chunk):
        res = client.post(
            "/api/files/upload",
            params={
                "location": loc,
                "name": name,
                "upload_id": "test-upload-1",
                "offset": offset,
                "total": len(data),
                **extra,
            },
            content=data[offset : offset + chunk],
            headers={"Content-Type": "application/octet-stream"},
        )
        answers.append(res)
        if res.status_code != 200:
            break
    return answers


def test_chunked_upload(api: tuple[TestClient, int], tree: Path) -> None:
    client, loc = api
    answers = upload(client, loc, "big.bin", b"0123456789", path="docs")
    assert [a.json()["received"] for a in answers] == [4, 8, 10]
    assert answers[-1].json()["entry"]["path"] == "docs/big.bin"
    assert (tree / "docs" / "big.bin").read_bytes() == b"0123456789"
    assert not list((tree / "docs").glob(".athena-upload-*"))
    # Taken names are refused unless overwriting.
    assert upload(client, loc, "big.bin", b"new", path="docs")[0].status_code == 409
    assert (
        upload(client, loc, "big.bin", b"new", path="docs", overwrite=True)[-1].status_code == 200
    )
    assert (tree / "docs" / "big.bin").read_bytes() == b"new"
    # Empty files work.
    assert upload(client, loc, "empty", b"")[0].json()["entry"]["size"] == 0


def test_upload_pieces_must_line_up(api: tuple[TestClient, int], tree: Path) -> None:
    client, loc = api
    params = {"location": loc, "name": "x.bin", "upload_id": "test-upload-2", "total": 8}
    send = lambda offset, data: client.post(  # noqa: E731
        "/api/files/upload", params={**params, "offset": offset}, content=data
    )
    assert send(0, b"abcd").status_code == 200
    res = send(2, b"zz")
    assert res.status_code == 409 and "byte 4" in res.json()["detail"]
    res = send(4, b"too long!")
    assert res.status_code == 400
    assert not (tree / ".athena-upload-test-upload-2").exists()
    assert send(0, b"abcd").status_code == 200
    res = client.delete("/api/files/upload", params={"location": loc, "upload_id": "test-upload-2"})
    assert res.status_code == 204
    assert not (tree / ".athena-upload-test-upload-2").exists()
    bad = {**params, "offset": 0, "name": "../escape"}
    assert client.post("/api/files/upload", params=bad, content=b"x").status_code == 400


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_permission_errors_are_reported(api: tuple[TestClient, int], tree: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores permissions")
    client, loc = api
    locked = tree / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        res = client.get("/api/files/list", params={"location": loc, "path": "locked"})
        assert res.status_code == 400 and "permission" in res.json()["detail"].lower()
    finally:
        locked.chmod(0o755)
