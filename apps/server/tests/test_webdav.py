import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import make_app, signed_in
from fastapi.testclient import TestClient
from test_files import audit_actions, symlink


@pytest.fixture
def dav(tmp_path: Path) -> Iterator[tuple[TestClient, tuple[str, str], Path, Path]]:
    one, two = tmp_path / "one", tmp_path / "two"
    (one / "docs").mkdir(parents=True)
    (one / "docs" / "a.txt").write_text("hello")
    (one / "page.html").write_text("<script>alert(1)</script>")
    (one / ".athena-upload-abcdefgh").write_text("part")
    two.mkdir()
    with TestClient(make_app(tmp_path)) as client:
        signed_in(client)
        for name, path in [("One", one), ("Two", two)]:
            res = client.post("/api/files/locations", json={"name": name, "path": str(path)})
            assert res.status_code == 201
        assert client.put("/api/webdav", json={"enabled": True}).status_code == 200
        pw = client.post("/api/webdav/password").json()
        yield client, (pw["username"], pw["password"]), one, two


def propfind(client: TestClient, path: str, auth, depth: str = "1"):
    return client.request("PROPFIND", path, headers={"Depth": depth}, auth=auth)


def hrefs(body: str) -> list[str]:
    return re.findall(r"<ns0:href>([^<]+)</ns0:href>", body)


def test_off_by_default(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path)) as client:
        signed_in(client)
        assert client.get("/api/webdav").json() == {
            "enabled": False,
            "path": "/dav/",
            "username": None,
            "has_password": False,
        }
        assert client.request("PROPFIND", "/dav/").status_code == 404
        # On without a password: nobody can sign in.
        client.put("/api/webdav", json={"enabled": True})
        assert client.request("PROPFIND", "/dav/", auth=("admin", "x")).status_code == 401


def test_sign_in(dav) -> None:
    client, auth, _, _ = dav
    assert propfind(client, "/dav/", None).status_code == 401
    assert propfind(client, "/dav/", (auth[0], "wrong")).status_code == 401
    assert propfind(client, "/dav/", ("someone", auth[1])).status_code == 401
    assert propfind(client, "/dav/", auth).status_code == 207
    # A new password replaces the old one at once, even though sign-ins are cached.
    new = client.post("/api/webdav/password").json()
    assert propfind(client, "/dav/", auth).status_code == 401
    assert propfind(client, "/dav/", (new["username"], new["password"])).status_code == 207
    client.put("/api/webdav", json={"enabled": False})
    assert propfind(client, "/dav/", (new["username"], new["password"])).status_code == 404
    actions = [a[1] for a in audit_actions(client) if a[0] == "settings.webdav"]
    assert actions == ["on", "new password", "new password", "off"]


def test_failed_sign_ins_are_throttled(dav) -> None:
    client, auth, _, _ = dav
    for _ in range(10):
        assert propfind(client, "/dav/", (auth[0], "wrong")).status_code == 401
    assert propfind(client, "/dav/", auth).status_code == 401


def test_browse_and_read(dav) -> None:
    client, auth, _, _ = dav
    res = propfind(client, "/dav/", auth)
    assert {"/dav/", "/dav/One/", "/dav/Two/"} <= set(hrefs(res.text))
    assert "<ns0:displayname>One</ns0:displayname>" in res.text
    res = propfind(client, "/dav/One/", auth)
    assert set(hrefs(res.text)) == {"/dav/One/", "/dav/One/docs/", "/dav/One/page.html"}

    res = client.get("/dav/One/docs/a.txt", auth=auth)
    assert res.status_code == 200 and res.text == "hello"
    # Served from Athena's origin, so a browser must never run it as part of the app.
    res = client.get("/dav/One/page.html", auth=auth)
    assert res.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert client.get("/dav/Nope/x", auth=auth).status_code == 404


def test_write_copy_move_delete(dav) -> None:
    client, auth, one, two = dav
    assert client.put("/dav/One/new.txt", content=b"new", auth=auth).status_code == 201
    assert (one / "new.txt").read_bytes() == b"new"
    assert client.request("MKCOL", "/dav/One/folder", auth=auth).status_code == 201
    assert (one / "folder").is_dir()
    res = client.request(
        "MOVE",
        "/dav/One/new.txt",
        headers={"Destination": "http://testserver/dav/Two/moved.txt"},
        auth=auth,
    )
    assert res.status_code == 201, res.text
    assert (two / "moved.txt").read_bytes() == b"new" and not (one / "new.txt").exists()
    res = client.request(
        "COPY", "/dav/One/docs/", headers={"Destination": "/dav/Two/docs/"}, auth=auth
    )
    assert res.status_code == 201
    assert (two / "docs" / "a.txt").read_text() == "hello"
    assert client.request("DELETE", "/dav/Two/docs/", auth=auth).status_code == 204
    assert not (two / "docs").exists()


def test_locations_themselves_are_protected(dav) -> None:
    client, auth, one, two = dav
    (two / "keep.txt").write_text("keep")
    assert client.request("DELETE", "/dav/One/", auth=auth).status_code == 403
    # Nothing inside was deleted either (wsgidav's fallback deletes item by item).
    assert (one / "docs" / "a.txt").read_text() == "hello"
    res = client.request("MOVE", "/dav/One/", headers={"Destination": "/dav/Moved/"}, auth=auth)
    assert res.status_code == 403
    # Replacing a location with something else would delete it first.
    res = client.request(
        "MOVE",
        "/dav/One/docs/",
        headers={"Destination": "/dav/Two/", "Overwrite": "T"},
        auth=auth,
    )
    assert res.status_code == 403
    # Copying a folder over a folder removes what the source doesn't have.
    res = client.request(
        "COPY", "/dav/One/docs/", headers={"Destination": "/dav/Two/", "Overwrite": "T"}, auth=auth
    )
    assert res.status_code == 403
    res = client.request(
        "COPY",
        "/dav/One/docs/a.txt",
        headers={"Destination": "/dav/Two", "Overwrite": "T"},
        auth=auth,
    )
    assert res.status_code == 403
    assert (two / "keep.txt").read_text() == "keep"
    assert (one / "docs" / "a.txt").read_text() == "hello"
    # Nothing can be created beside the locations.
    assert client.request("MKCOL", "/dav/Other", auth=auth).status_code == 403
    assert client.put("/dav/file.txt", content=b"x", auth=auth).status_code == 403


def test_paths_stay_inside(dav, tmp_path: Path) -> None:
    client, auth, one, _ = dav
    (tmp_path / "outside.txt").write_text("secret")
    symlink(one / "link.txt", tmp_path / "outside.txt")
    symlink(one / "linkdir", tmp_path)
    listed = hrefs(propfind(client, "/dav/One/", auth).text)
    assert "/dav/One/link.txt" not in listed and "/dav/One/linkdir/" not in listed
    # Uploads in progress from the file manager are hidden too.
    assert not any("athena-upload" in h for h in listed)
    assert client.get("/dav/One/link.txt", auth=auth).status_code == 403
    assert client.get("/dav/One/linkdir/outside.txt", auth=auth).status_code == 403
    assert client.put("/dav/One/linkdir/new.txt", content=b"x", auth=auth).status_code == 403
    assert not (tmp_path / "new.txt").exists()
    for bad in ["/dav/One/docs/%2e%2e/%2e%2e/outside.txt", "/dav/One/..%2foutside.txt"]:
        assert client.get(bad, auth=auth).status_code in (400, 403, 404), bad


def test_settings_need_an_admin_session(dav) -> None:
    client, _, _, _ = dav
    other = TestClient(client.app)
    assert other.get("/api/webdav").status_code == 401
    assert other.post("/api/webdav/password").status_code == 401


def test_cached_sign_ins_still_check_the_password(dav) -> None:
    client, auth, _, _ = dav
    assert propfind(client, "/dav/", auth).status_code == 207  # now cached
    assert propfind(client, "/dav/", (auth[0], auth[1] + "x")).status_code == 401
    assert propfind(client, "/dav/", ("ädmin", "pässword")).status_code == 401
    assert propfind(client, "/dav/", auth).status_code == 207
