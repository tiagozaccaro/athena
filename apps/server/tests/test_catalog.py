import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import make_app, signed_in
from fastapi.testclient import TestClient
from test_containers import ready_store

import athena.api.apps as apps_api
from athena.catalog.loader import (
    InstallValueError,
    builtin_catalog_dir,
    env_file,
    load_catalog,
    resolve_values,
)
from athena.catalog.model import InvalidCatalogAppError, parse_app
from athena.catalog.registry import CatalogRegistry

# ---------------------------------------------------------------- the built-in catalog


def builtin():
    root = builtin_catalog_dir()
    assert root is not None, "catalog/ not found"
    return load_catalog(root, "builtin")


def test_builtin_catalog_loads_without_errors() -> None:
    apps, errors = builtin()
    assert errors == []
    assert len(apps) >= 20
    assert len({a.id for a in apps}) == len(apps)


def test_every_builtin_app_installs_with_defaults(tmp_path: Path) -> None:
    apps, _ = builtin()
    for app in apps:
        values = resolve_values(app, {}, tmp_path / app.id / "data")
        assert set(values) == {f.key for f in app.meta.env}, app.id
        for f in app.meta.env:
            if f.generate == "secret":
                assert len(values[f.key]) >= 24, f"{app.id}: {f.key} not generated"


def test_builtin_web_ports_dont_clash() -> None:
    apps, _ = builtin()
    seen: dict[str, str] = {}
    for app in apps:
        ports = {f.default for f in app.meta.env if f.key == "WEB_PORT"}
        for port in ports:
            assert port not in seen, f"{app.id} and {seen.get(port)} both default to {port}"
            seen[port or ""] = app.id


def _engine() -> list[str] | None:
    if os.environ.get("ATHENA_DOCKER_TESTS") != "1" or not shutil.which("docker"):
        return None
    from athena.containers.runtime import RuntimeUnavailableError, runtime_from
    from athena.platform.detect import detect

    try:
        return list(runtime_from(detect().get("containers")).cli)
    except RuntimeUnavailableError:
        return None


@pytest.mark.skipif(_engine() is None, reason="set ATHENA_DOCKER_TESTS=1 with a running engine")
def test_every_builtin_app_passes_compose_config(tmp_path: Path) -> None:
    cli = _engine()
    assert cli is not None
    apps, _ = builtin()
    failures = []
    for app in apps:
        folder = tmp_path / app.id
        folder.mkdir()
        (folder / "compose.yaml").write_text(app.compose)
        (folder / ".env").write_text(env_file(resolve_values(app, {}, folder / "data")))
        result = subprocess.run(
            [*cli, "compose", "--file", str(folder / "compose.yaml"), "config", "--quiet"],
            capture_output=True,
            text=True,
            env={**os.environ, "ATHENA_APP_DATA": str(folder / "data")},
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"{app.id}: {result.stderr.strip()}")
    assert failures == []


# ---------------------------------------------------------------- format rules


def doc(env: list[dict], compose_vars: str = "${WEB_PORT}") -> tuple[str, dict]:
    text = f"services:\n  a:\n    image: x:1\n    ports: ['{compose_vars}:80']\n"
    return text, {
        "x-athena": {
            "title": "A",
            "description": "d",
            "category": "utilities",
            "web_port": "WEB_PORT",
            "env": env,
        },
        "services": {"a": {"image": "x:1"}},
    }


PORT = {"key": "WEB_PORT", "label": "Port", "type": "port", "default": "8080"}


def test_undeclared_variables_are_rejected() -> None:
    text, d = doc([PORT], "${WEB_PORT}:${OTHER}")
    with pytest.raises(InvalidCatalogAppError, match="undeclared variables OTHER"):
        parse_app("a", "builtin", text, d)


def test_web_port_must_be_a_field() -> None:
    text, d = doc([{**PORT, "key": "PORT"}], "${PORT}")
    with pytest.raises(InvalidCatalogAppError, match="web_port"):
        parse_app("a", "builtin", text, d)


def test_missing_metadata() -> None:
    with pytest.raises(InvalidCatalogAppError, match="x-athena"):
        parse_app("a", "builtin", "services: {}", {"services": {}})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (PORT, "70000", "port number"),
        (PORT, "abc", "port number"),
        ({"key": "P", "label": "P", "type": "path"}, "relative/dir", "absolute"),
        ({"key": "B", "label": "B", "type": "boolean"}, "yes", "true or false"),
        ({"key": "S", "label": "S", "type": "select", "options": ["a", "b"]}, "c", "one of"),
        ({"key": "T", "label": "T"}, "", "Required"),
        ({"key": "T", "label": "T"}, "two\nlines", "single line"),
    ],
)
def test_value_validation(field: dict, value: str, message: str, tmp_path: Path) -> None:
    env = [PORT] if field is PORT else [PORT, field]
    text, d = doc(env)
    app = parse_app("a", "builtin", text, d)
    with pytest.raises(InstallValueError) as exc:
        resolve_values(app, {field["key"]: value}, tmp_path)
    assert message in exc.value.errors[field["key"]]


def test_default_tokens(tmp_path: Path) -> None:
    text, d = doc(
        [
            PORT,
            {"key": "TZ", "label": "TZ", "default": "@timezone"},
            {"key": "DATA", "label": "D", "type": "path", "default": "@app_data/media"},
            {"key": "UID", "label": "U", "default": "@uid"},
        ]
    )
    values = resolve_values(parse_app("a", "builtin", text, d), {}, tmp_path)
    assert values["TZ"]
    assert values["DATA"] == str(tmp_path / "media")
    assert values["UID"].isdigit() and values["UID"] != "0"


def test_env_file_quoting() -> None:
    rendered = env_file({"A": "plain", "B": "pa$$word", "C": "it's"})
    assert "A='plain'" in rendered
    assert "B='pa$$word'" in rendered  # single quotes: literal, no interpolation
    assert 'C="it\'s"' in rendered


# ---------------------------------------------------------------- store API


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import sys

    monkeypatch.setattr("athena.containers.runtime.shutil.which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr("athena.containers.service.list_containers", lambda rt: [])
    monkeypatch.setattr(
        apps_api,
        "compose",
        lambda runtime, name, path, *args: [sys.executable, "-c", "print('ok')"],
    )
    with TestClient(make_app(tmp_path, store=ready_store())) as client:
        yield signed_in(client)


def test_store_lists_and_filters(api: TestClient) -> None:
    apps = api.get("/api/store/apps").json()
    assert len(apps) >= 20
    media = api.get("/api/store/apps", params={"category": "media"}).json()
    assert media and all(a["category"] == "media" for a in media)
    found = api.get("/api/store/apps", params={"q": "jelly"}).json()
    assert [a["id"] for a in found] == ["jellyfin"]
    cats = api.get("/api/store/categories").json()
    assert sum(c["count"] for c in cats) == len(apps)


def test_store_detail_has_resolved_form(api: TestClient, tmp_path: Path) -> None:
    detail = api.get("/api/store/apps/builtin/nextcloud").json()
    assert detail["suggested_name"] == "nextcloud"
    fields = {f["key"]: f for f in detail["fields"]}
    assert fields["DB_PASSWORD"]["generated"] is True
    assert fields["DB_PASSWORD"]["default"] == ""
    jelly = {f["key"]: f for f in api.get("/api/store/apps/builtin/jellyfin").json()["fields"]}
    assert jelly["MEDIA_PATH"]["default"].endswith("apps/jellyfin/data/media")
    assert api.get("/api/store/apps/builtin/nope").status_code == 404


def test_install_writes_env_and_deploys(api: TestClient, tmp_path: Path) -> None:
    res = api.post(
        "/api/store/apps/builtin/nextcloud/install",
        json={"name": "cloud", "values": {"WEB_PORT": "9999"}},
    )
    assert res.status_code == 202, res.text
    from test_apps import wait

    assert wait(api, res.json()["id"])["status"] == "succeeded"
    app_dir = tmp_path / "data" / "apps" / "cloud"
    env = (app_dir / ".env").read_text()
    assert "WEB_PORT='9999'" in env
    assert "DB_PASSWORD='" in env and "DB_PASSWORD=''" not in env
    if os.name == "posix":
        assert (app_dir / ".env").stat().st_mode & 0o777 == 0o600

    listed = api.get("/api/apps").json()[0]
    assert (listed["source"], listed["catalog_id"]) == ("catalog", "builtin/nextcloud")
    assert listed["web_port"] == 9999
    store = api.get("/api/store/apps", params={"q": "nextcloud"}).json()[0]
    assert store["installed"] == ["cloud"]
    # The suggested name skips taken names.
    assert api.get("/api/store/apps/builtin/nextcloud").json()["suggested_name"] == "nextcloud"


def test_install_rejects_bad_values(api: TestClient) -> None:
    res = api.post(
        "/api/store/apps/builtin/jellyfin/install",
        json={"name": "jf", "values": {"WEB_PORT": "99999"}},
    )
    assert res.status_code == 422
    assert "WEB_PORT" in res.json()["detail"]["errors"]
    assert api.get("/api/apps").json() == []


def test_registry_with_given_apps() -> None:
    apps, _ = builtin()
    registry = CatalogRegistry(apps[:2])
    assert len(registry.all()) == 2


def test_read_env_round_trips(tmp_path: Path) -> None:
    from athena.apps.store import AppStore

    store = AppStore(tmp_path)
    values = {"A": "plain", "B": "pa$$word", "C": "it's", "D": 'q"$x'}
    store.write_env("x", env_file(values))
    assert store.read_env("x") == values
