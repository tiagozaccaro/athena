import io
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest
import yaml
from conftest import make_app, signed_in
from fastapi.testclient import TestClient
from test_apps import wait
from test_containers import ready_store

import athena.api.apps as apps_api
from athena.catalog import remote
from athena.catalog.casaos import convert
from athena.catalog.loader import resolve_values

FIXTURES = Path(__file__).parent / "fixtures" / "casaos"


# ---------------------------------------------------------------- CasaOS conversion


def casaos(name: str):
    return convert(name, (FIXTURES / f"{name}.yml").read_text(encoding="utf-8"), "casaos")


def test_jellyfin_conventions_are_mapped(tmp_path: Path) -> None:
    app = casaos("Jellyfin")
    assert app.id == "jellyfin"
    assert app.meta.title == "Jellyfin"
    assert app.meta.category == "media"
    assert app.meta.web_port == "WEB_PORT"
    fields = {f.key: f for f in app.meta.env}
    assert next(iter(fields)) == "WEB_PORT"
    assert fields["WEB_PORT"].default == "8097"
    assert (fields["PUID"].default, fields["PGID"].default, fields["TZ"].default) == (
        "@uid",
        "@gid",
        "@timezone",
    )
    assert fields["MEDIA_PATH"].type == "path"
    assert "/DATA/" not in app.compose and "$AppID" not in app.compose
    assert "${ATHENA_APP_DATA}/config" in app.compose
    assert "x-casaos" not in app.compose
    values = resolve_values(app, {}, tmp_path)
    assert values["MEDIA_PATH"] == str(tmp_path / "media")


@pytest.mark.parametrize("name", ["Jellyfin", "Vaultwarden", "Nextcloud"])
def test_fixtures_convert_to_valid_catalog_apps(name: str) -> None:
    app = casaos(name)
    doc = yaml.safe_load(app.compose)
    main = next(iter(doc["services"].values()))
    published = [p.get("published") for p in main.get("ports", []) if isinstance(p, dict)]
    assert "${WEB_PORT}" in published


def test_other_variables_become_fields() -> None:
    text = (
        "x-casaos: {title: {en_US: Thing}, category: Developer, port_map: '8080', main: web}\n"
        "services:\n"
        "  web:\n"
        "    image: thing:1\n"
        "    ports: ['8080:80']\n"
        "    environment:\n"
        "      ADMIN_PASSWORD: $default_pwd\n"
        "      DOMAIN: ${domain}\n"
        "      LITERAL: cost $$5\n"
        "    command: [run, --appendonly, yes]\n"
    )
    app = convert("Thing", text, "c")
    fields = {f.key: f for f in app.meta.env}
    assert fields["DEFAULT_PWD"].type == "password"
    assert fields["DEFAULT_PWD"].generate == "secret"
    assert fields["DOMAIN"].required is False
    assert app.meta.category == "development"
    doc = yaml.safe_load(app.compose)
    web = doc["services"]["web"]
    assert web["ports"] == ["${WEB_PORT}:80"]
    assert web["environment"]["LITERAL"] == "cost $$5"
    assert web["command"][-1] == "yes"  # YAML 1.2: stays a string, as compose reads it


# ---------------------------------------------------------------- remote fetching


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/IceWhaleTech/CasaOS-AppStore",
            "https://github.com/IceWhaleTech/CasaOS-AppStore/archive/HEAD.tar.gz",
        ),
        (
            "https://github.com/o/r.git",
            "https://github.com/o/r/archive/HEAD.tar.gz",
        ),
        (
            "https://github.com/o/r/tree/dev",
            "https://github.com/o/r/archive/refs/heads/dev.tar.gz",
        ),
        ("https://codeberg.org/o/r", "https://codeberg.org/o/r/archive/main.tar.gz"),
        (
            "https://gitlab.com/o/r",
            "https://gitlab.com/o/r/-/archive/main/r-main.tar.gz",
        ),
        ("https://example.com/store.zip", "https://example.com/store.zip"),
    ],
)
def test_archive_urls(url: str, expected: str) -> None:
    assert remote.archive_url(url) == expected


@pytest.mark.parametrize("url", ["http://github.com/o/r", "https://example.com/page", "ftp://x"])
def test_bad_urls(url: str) -> None:
    with pytest.raises(remote.CatalogFetchError):
        remote.archive_url(url)


def _tar(path: Path, files: dict[str, str]) -> None:
    with tarfile.open(path, "w:gz") as tf:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def test_tar_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "evil.tar.gz"
    _tar(archive, {"../../escape.txt": "x"})
    with pytest.raises(tarfile.TarError):
        remote.extract(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_zip_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "x")
    with pytest.raises(remote.CatalogFetchError, match="Unsafe path"):
        remote.extract(archive, tmp_path / "out")


def test_not_an_archive(tmp_path: Path) -> None:
    junk = tmp_path / "junk"
    junk.write_text("<html>")
    with pytest.raises(remote.CatalogFetchError, match="archive"):
        remote.extract(junk, tmp_path / "out")


def casaos_tree() -> dict[str, str]:
    """A CasaOS store nested like its release zip."""
    base = "build/sysroot/var/lib/casaos/appstore/default.new/Apps"
    return {
        f"{base}/{n}/docker-compose.yml": (FIXTURES / f"{n}.yml").read_text(encoding="utf-8")
        for n in (
            "Jellyfin",
            "Vaultwarden",
        )
    }


ATHENA_APP = (
    Path(__file__).parents[3] / "catalog" / "apps" / "it-tools" / "compose.yaml"
).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("files", "kind", "count"),
    [
        (casaos_tree(), "casaos", 2),
        ({"repo-main/apps/it-tools/compose.yaml": ATHENA_APP}, "athena", 1),
    ],
)
def test_refresh_end_to_end(
    files: dict[str, str], kind: str, count: int, tmp_path: Path, monkeypatch
) -> None:
    archive = tmp_path / "src.tar.gz"
    _tar(archive, files)
    monkeypatch.setattr(remote, "download", lambda url, dest, log: shutil.copyfile(archive, dest))
    lines: list[str] = []
    dest = tmp_path / "catalogs" / "x"
    assert remote.refresh("https://github.com/o/r", "auto", "x", dest, lines.append) == count
    assert f"Catalog format: {kind}" in lines
    # A second refresh replaces the folder atomically.
    assert remote.refresh("https://github.com/o/r", "auto", "x", dest, lines.append) == count
    assert not dest.with_name("x.old").exists()


def test_refresh_without_apps_keeps_the_old_copy(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "empty.tar.gz"
    _tar(archive, {"README.md": "nothing here"})
    monkeypatch.setattr(remote, "download", lambda url, dest, log: shutil.copyfile(archive, dest))
    dest = tmp_path / "catalogs" / "x"
    (dest / "apps" / "keep").mkdir(parents=True)
    with pytest.raises(remote.CatalogFetchError, match="No apps found"):
        remote.refresh("https://github.com/o/r", "auto", "x", dest, print)
    assert (dest / "apps" / "keep").is_dir()


# ---------------------------------------------------------------- API


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    archive = tmp_path / "store.tar.gz"
    _tar(archive, casaos_tree())
    monkeypatch.setattr(remote, "download", lambda url, dest, log: shutil.copyfile(archive, dest))
    monkeypatch.setattr("athena.containers.runtime.shutil.which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr("athena.containers.service.list_containers", lambda rt: [])
    monkeypatch.setattr(
        apps_api, "compose", lambda runtime, name, path, *args: [sys.executable, "-c", "print(1)"]
    )
    with TestClient(make_app(tmp_path, store=ready_store())) as client:
        yield signed_in(client)


def test_catalog_lifecycle(api: TestClient, tmp_path: Path) -> None:
    before = len(api.get("/api/store/apps").json())
    res = api.post(
        "/api/store/catalogs",
        json={"name": "CasaOS AppStore", "url": "https://github.com/IceWhaleTech/CasaOS-AppStore"},
    )
    assert res.status_code == 202, res.text
    assert wait(api, res.json()["id"])["status"] == "succeeded"

    catalogs = {c["id"]: c for c in api.get("/api/store/catalogs").json()}
    assert catalogs["builtin"]["builtin"] is True
    added = catalogs["casaos-appstore"]
    assert (added["app_count"], added["error"]) == (2, None)
    assert added["refreshed_at"]

    apps = api.get("/api/store/apps").json()
    assert len(apps) == before + 2
    imported = [a for a in apps if a["catalog"] == "casaos-appstore"]
    assert {a["catalog_name"] for a in imported} == {"CasaOS AppStore"}
    detail = api.get("/api/store/apps/casaos-appstore/jellyfin").json()
    assert detail["fields"][0]["key"] == "WEB_PORT"

    dup = api.post(
        "/api/store/catalogs",
        json={"name": "Again", "url": "https://github.com/IceWhaleTech/CasaOS-AppStore"},
    )
    assert dup.status_code == 409
    assert wait(api, api.post("/api/store/catalogs/casaos-appstore/refresh").json()["id"])[
        "status"
    ] == ("succeeded")

    assert api.delete("/api/store/catalogs/casaos-appstore").status_code == 204
    assert len(api.get("/api/store/apps").json()) == before
    assert not (tmp_path / "data" / "catalogs" / "casaos-appstore").exists()


def test_failed_refresh_records_the_error(api: TestClient, monkeypatch) -> None:
    def boom(url, dest, log):
        raise remote.CatalogFetchError("Download failed: HTTP Error 404")

    monkeypatch.setattr(remote, "download", boom)
    res = api.post("/api/store/catalogs", json={"name": "Gone", "url": "https://github.com/a/b"})
    job = wait(api, res.json()["id"])
    assert job["status"] == "failed"
    gone = next(c for c in api.get("/api/store/catalogs").json() if c["id"] == "gone")
    assert "404" in gone["error"]


def test_add_catalog_rejects_bad_urls(api: TestClient) -> None:
    res = api.post("/api/store/catalogs", json={"name": "X", "url": "https://example.com/x"})
    assert res.status_code == 422


def test_edit_env_and_redeploy(api: TestClient, tmp_path: Path) -> None:
    job = api.post(
        "/api/store/apps/builtin/it-tools/install", json={"name": "tools", "values": {}}
    ).json()
    wait(api, job["id"])
    detail = api.get("/api/apps/tools").json()
    assert "WEB_PORT='8086'" in detail["env"]

    edited = detail["env"].replace("8086", "8099")
    res = api.put("/api/apps/tools/env", json={"env": edited})
    assert res.status_code == 202
    assert wait(api, res.json()["id"])["status"] == "succeeded"
    assert api.get("/api/apps/tools").json()["web_port"] == 8099

    bad = api.put("/api/apps/tools/env", json={"env": "WEB_PORT='1'\nnot a valid line\n"})
    assert bad.status_code == 422
    assert "Lines 2" in bad.json()["detail"]


def test_apps_without_env_report_none(api: TestClient) -> None:
    compose = "services:\n  a:\n    image: busybox:1.37\n"
    wait(api, api.post("/api/apps", json={"name": "plain", "compose": compose}).json()["id"])
    assert api.get("/api/apps/plain").json()["env"] is None
