import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import make_app, signed_in
from fastapi.testclient import TestClient
from test_containers import ready_store

import athena.api.apps as apps_api
from athena.catalog import image_platforms as ip
from athena.catalog.loader import (
    InstallValueError,
    builtin_catalog_dir,
    env_file,
    load_catalog,
    resolve_values,
)
from athena.catalog.model import CATEGORY_LABELS, InvalidCatalogAppError, parse_app
from athena.catalog.platforms import KNOWN_PLATFORMS, host_platform, support
from athena.catalog.registry import CatalogRegistry

# ---------------------------------------------------------------- the built-in catalog


def builtin():
    root = builtin_catalog_dir()
    assert root is not None, "catalog/ not found"
    return load_catalog(root, "builtin")


def user_entries(app) -> dict[str, str]:
    """What a user must type: required fields with no default or generated value (a token)."""
    return {
        f.key: "user-entered"
        for f in app.meta.env
        if f.required and not f.default and not f.generate
    }


def test_builtin_catalog_loads_without_errors() -> None:
    apps, errors = builtin()
    assert errors == []
    assert len(apps) >= 20
    assert len({a.id for a in apps}) == len(apps)


def test_every_builtin_app_installs_with_defaults(tmp_path: Path) -> None:
    apps, _ = builtin()
    for app in apps:
        values = resolve_values(app.meta.env, user_entries(app), tmp_path / app.id / "data")
        assert set(values) == {f.key for f in app.meta.env}, app.id
        for f in app.meta.env:
            if f.generate == "secret":
                assert len(values[f.key]) >= 24, f"{app.id}: {f.key} not generated"
            elif f.generate:
                size = {"hex16": 32, "hex32": 64}[f.generate]
                assert len(values[f.key]) == size, f"{app.id}: {f.key} not generated"
                int(values[f.key], 16)


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
        values = resolve_values(app.meta.env, user_entries(app), folder / "data")
        (folder / ".env").write_text(env_file(values))
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
        parse_app("a", "builtin", [("compose.yaml", text, d)])


def test_web_port_must_be_a_field() -> None:
    text, d = doc([{**PORT, "key": "PORT"}], "${PORT}")
    with pytest.raises(InvalidCatalogAppError, match="web_port"):
        parse_app("a", "builtin", [("compose.yaml", text, d)])


def test_missing_metadata() -> None:
    with pytest.raises(InvalidCatalogAppError, match="x-athena"):
        parse_app("a", "builtin", [("compose.yaml", "services: {}", {"services": {}})])


def test_multiple_compose_files_expose_installable_variants() -> None:
    default_text, default_d = doc([PORT], "${WEB_PORT}:80")
    variant_text, variant_d = doc(
        [PORT, {"key": "EXTRA", "label": "Extra", "default": "x"}],
        "${WEB_PORT}:81",
    )
    app = parse_app(
        "a",
        "builtin",
        [
            ("compose.yaml", default_text, default_d),
            ("compose.extra.yaml", variant_text, variant_d),
        ],
    )
    assert len(app.variants) == 2
    assert app.variants[0].slug == "default"
    assert app.variants[1].slug == "extra"
    assert app.variants[1].label == "Extra"
    assert [f.key for f in app.variants[1].env] == ["WEB_PORT", "EXTRA"]
    assert app.variants[1].web_port == "WEB_PORT"
    assert app.images == ["x:1"]
    assert app.variants[1].images == ["x:1"]
    # The app-level compose/images come from the default variant.
    assert app.compose == default_text


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
    app = parse_app("a", "builtin", [("compose.yaml", text, d)])
    with pytest.raises(InstallValueError) as exc:
        resolve_values(app.meta.env, {field["key"]: value}, tmp_path)
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
    app = parse_app("a", "builtin", [("compose.yaml", text, d)])
    values = resolve_values(app.meta.env, {}, tmp_path)
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
    assert "jellyfin" in [a["id"] for a in found]
    tagged = api.get("/api/store/apps", params={"q": "bittorrent"}).json()
    assert {"deluge", "qbittorrent", "transmission"} <= {a["id"] for a in tagged}
    cats = api.get("/api/store/categories").json()
    assert sum(c["count"] for c in cats) == len(apps)
    # Every category has apps, so none is hidden from the filter by being empty.
    assert [c["id"] for c in cats] == list(CATEGORY_LABELS)


def test_store_detail_has_resolved_form(api: TestClient, tmp_path: Path) -> None:
    detail = api.get("/api/store/apps/builtin/nextcloud").json()
    assert detail["suggested_name"] == "nextcloud"
    fields = {f["key"]: f for f in detail["fields"]}
    assert fields["DB_PASSWORD"]["generated"] is True
    assert fields["DB_PASSWORD"]["default"] == ""
    jelly = {f["key"]: f for f in api.get("/api/store/apps/builtin/jellyfin").json()["fields"]}
    assert Path(jelly["MEDIA_PATH"]["default"]).parts[-4:] == ("apps", "jellyfin", "data", "media")
    assert api.get("/api/store/apps/builtin/nope").status_code == 404


def test_store_front_metadata(api: TestClient) -> None:
    apps = api.get("/api/store/apps").json()
    by_id = {a["id"]: a for a in apps}
    popular = {a["id"] for a in apps if a["popular"]}
    assert {"jellyfin", "immich", "nextcloud"} <= popular

    gitea = by_id["gitea"]
    assert gitea["tagline"] and gitea["tags"] and gitea["category_label"] == "Development"
    assert gitea["cover"] and gitea["cover"].startswith("https://")

    detail = api.get("/api/store/apps/builtin/gitea").json()
    assert detail["features"] and len(detail["screenshots"]) >= 2
    assert detail["cover"] == detail["screenshots"][0]
    assert detail["license"] == "MIT"

    # Apps without screenshots fall back to their icon on a card.
    assert by_id["deluge"]["cover"] is None
    assert by_id["deluge"]["tagline"]


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
    assert listed["title"] == "Nextcloud"
    assert listed["icon"].endswith(".svg")
    store = api.get("/api/store/apps", params={"q": "nextcloud"}).json()[0]
    assert store["installed"] == ["cloud"]
    # The suggested name skips taken names.
    assert api.get("/api/store/apps/builtin/nextcloud").json()["suggested_name"] == "nextcloud"


def test_install_selects_variant_compose(api: TestClient, tmp_path: Path) -> None:
    detail = api.get("/api/store/apps/builtin/freshrss").json()
    assert {v["slug"] for v in detail["variants"]} == {"default", "postgres"}
    assert {v["label"] for v in detail["variants"]} == {"Default", "PostgreSQL"}
    # Default variant has no DB_PASSWORD; the postgres variant does.
    default_fields = {f["key"]: f for f in detail["fields"]}
    assert "DB_PASSWORD" not in default_fields
    postgres = next(v for v in detail["variants"] if v["slug"] == "postgres")
    assert "DB_PASSWORD" in {f["key"] for f in postgres["fields"]}

    from test_apps import wait

    res = api.post(
        "/api/store/apps/builtin/freshrss/install",
        json={"name": "freshrss-db", "values": {"WEB_PORT": "9999"}, "variant": "postgres"},
    )
    assert res.status_code == 202, res.text
    assert wait(api, res.json()["id"])["status"] == "succeeded"
    app_dir = tmp_path / "data" / "apps" / "freshrss-db"
    compose = (app_dir / "compose.yaml").read_text()
    assert "postgres:" in compose
    assert "FRESHRSS_INSTALL" in compose
    assert "--db-type pgsql" in compose
    env = (app_dir / ".env").read_text()
    assert "DB_PASSWORD='" in env and "DB_PASSWORD=''" not in env


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


# ---------------------------------------------------------------- platforms (host CPU)

# Apps whose images can't be read from their registry yet (a wrong tag or name, or a
# private package), so the platform script can't fill them in. Remove an id once its
# image is fixed and `python -m athena.catalog.image_platforms <id> --write` has run.
UNREADABLE: set[str] = set()


@pytest.mark.parametrize(
    ("platforms", "os_", "arch", "expected"),
    [
        (["linux/amd64", "linux/arm64"], "linux", "x86_64", "native"),
        (["linux/amd64", "linux/arm64"], "linux", "aarch64", "native"),
        (["linux/amd64"], "linux", "aarch64", "unsupported"),
        (["linux/amd64"], "darwin", "arm64", "emulated"),
        (["linux/amd64"], "windows", "arm64", "emulated"),
        (["linux/arm64"], "windows", "amd64", "unsupported"),
        (["linux/amd64", "linux/arm64"], "linux", "armv7l", "unsupported"),
        (["linux/arm"], "linux", "armv7l", "native"),
        (["linux/amd64"], "linux", "riscv64", "native"),  # unknown CPU: don't block
    ],
)
def test_support(platforms: list[str], os_: str, arch: str, expected: str) -> None:
    assert support(platforms, os_, arch) == expected


def test_host_platform() -> None:
    assert host_platform("x86_64") == host_platform("AMD64") == "linux/amd64"
    assert host_platform("aarch64") == host_platform("arm64") == "linux/arm64"
    assert host_platform("armv7l") == "linux/arm/v7"
    assert host_platform("mips") is None


def _declares_platforms(app_id: str) -> bool:
    root = builtin_catalog_dir()
    assert root is not None
    return bool(ip.DECLARED.search((root / "apps" / app_id / "compose.yaml").read_text("utf-8")))


def test_builtin_apps_declare_their_platforms() -> None:
    apps, _ = builtin()
    missing = sorted(a.id for a in apps if a.id not in UNREADABLE and not _declares_platforms(a.id))
    assert missing == [], "run `uv run python -m athena.catalog.image_platforms --write`"
    for app in apps:
        assert app.meta.platforms, app.id
        assert set(app.meta.platforms) <= set(KNOWN_PLATFORMS), app.id


@pytest.mark.skipif(
    os.environ.get("ATHENA_NETWORK_TESTS") != "1",
    reason="set ATHENA_NETWORK_TESTS=1 to read the image registries",
)
def test_builtin_platforms_match_the_registries() -> None:
    apps, _ = builtin()
    results = ip.lookup_apps(apps)
    wrong = [
        f"{r.app.id}: declares {r.app.meta.platforms}, registry has {r.platforms}"
        for r in results
        if r.app.id not in UNREADABLE
        and r.platforms is not None
        and r.platforms != r.app.meta.platforms
    ]
    unreadable = [
        f"{r.app.id}: {r.errors}"
        for r in results
        if r.platforms is None and r.app.id not in UNREADABLE
    ]
    readable_now = sorted(
        r.app.id for r in results if r.platforms is not None and r.app.id in UNREADABLE
    )
    assert wrong == [], "run `uv run python -m athena.catalog.image_platforms --write`"
    assert unreadable == []
    assert readable_now == [], "these images can be read now: drop them from UNREADABLE"


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("nginx", ("docker.io", "library/nginx", "latest")),
        ("postgres:16-alpine", ("docker.io", "library/postgres", "16-alpine")),
        ("linuxserver/sonarr:4", ("docker.io", "linuxserver/sonarr", "4")),
        ("lscr.io/linuxserver/sonarr:4", ("ghcr.io", "linuxserver/sonarr", "4")),
        ("ghcr.io/a/b@sha256:abc", ("ghcr.io", "a/b", "sha256:abc")),
        ("localhost:5000/a:1", ("localhost:5000", "a", "1")),
    ],
)
def test_parse_image(image: str, expected: tuple[str, str, str]) -> None:
    ref = ip.parse_image(image)
    assert (ref.registry, ref.repository, ref.reference) == expected


def test_lookup_reads_indexes_single_images_and_docker_hub() -> None:
    import httpx2

    def handle(req: httpx2.Request) -> httpx2.Response:
        url = str(req.url)
        if url.startswith("https://hub.docker.com/v2/repositories/library/redis/tags/8"):
            images = [
                {"os": "linux", "architecture": "amd64"},
                {"os": "linux", "architecture": "arm64", "variant": "v8"},
                {"os": "linux", "architecture": "arm", "variant": "v7"},
                {"os": "linux", "architecture": "s390x"},
            ]
            return httpx2.Response(200, json={"images": images})
        if url.startswith("https://ghcr.io/token"):
            assert req.url.params["scope"] == "repository:a/multi:pull"
            return httpx2.Response(200, json={"token": "t"})
        if not req.headers.get("authorization"):
            challenge = 'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:a/multi:pull"'
            return httpx2.Response(401, headers={"www-authenticate": challenge})
        if url == "https://ghcr.io/v2/a/multi/manifests/1":
            manifests = [
                {"platform": {"os": "linux", "architecture": "amd64"}},
                {"platform": {"os": "linux", "architecture": "arm64"}},
                {"platform": {"os": "unknown", "architecture": "unknown"}},
            ]
            return httpx2.Response(200, json={"manifests": manifests})
        if url == "https://ghcr.io/v2/a/single/manifests/1":
            return httpx2.Response(200, json={"config": {"digest": "sha256:c"}})
        if url == "https://ghcr.io/v2/a/single/blobs/sha256:c":
            return httpx2.Response(200, json={"os": "linux", "architecture": "amd64"})
        return httpx2.Response(404)

    def app(app_id: str, images: list[str]):
        text = "services:\n" + "".join(f"  s{i}:\n    image: {im}\n" for i, im in enumerate(images))
        d = {
            "x-athena": {"title": "A", "description": "d", "category": "utilities"},
            "services": {f"s{i}": {"image": im} for i, im in enumerate(images)},
        }
        return parse_app(app_id, "builtin", [("compose.yaml", text, d)])

    results = ip.lookup_apps(
        [
            app("multi", ["ghcr.io/a/multi:1", "redis:8"]),
            app("single", ["ghcr.io/a/single:1", "redis:8"]),
            app("broken", ["ghcr.io/a/missing:1"]),
        ],
        transport=httpx2.MockTransport(handle),
    )
    by_id = {r.app.id: r for r in results}
    assert by_id["multi"].platforms == ["linux/amd64", "linux/arm64"]
    assert by_id["single"].platforms == ["linux/amd64"]
    assert by_id["broken"].platforms is None
    assert "not found" in by_id["broken"].errors["ghcr.io/a/missing:1"]


def test_set_platforms_rewrites_only_the_key() -> None:
    block = (
        "# header\nx-athena:\n  title: A\n  category: media\n  platforms:\n  - linux/amd64\n"
        "  - linux/arm64\n  notes: hi\nservices:\n  a:\n    image: x\n"
    )
    out = ip.set_platforms(block, ["linux/amd64"])
    assert out == block.replace(
        "  platforms:\n  - linux/amd64\n  - linux/arm64\n", "  platforms: [linux/amd64]\n"
    )
    flow = "x-athena:\n  title: A\n  platforms: [linux/amd64]\n  env: []\nservices: {}\n"
    assert "platforms: [linux/amd64, linux/arm64]\n  env" in ip.set_platforms(
        flow, ["linux/amd64", "linux/arm64"]
    )
    missing = "x-athena:\n  title: A\n  category: media\n  icon: i\nservices: {}\n"
    assert ip.set_platforms(missing, ["linux/arm64"]) == missing.replace(
        "  category: media\n", "  category: media\n  platforms: [linux/arm64]\n"
    )
    # A `platforms:` key under a service isn't touched.
    nested = "x-athena:\n  title: A\nservices:\n  a:\n    platforms: x\n"
    assert ip.set_platforms(nested, ["linux/amd64"]).count("platforms") == 2


def _store_for(os_: str, arch: str):
    from athena.platform.store import CapabilityStore

    base = ready_store()._detector
    return CapabilityStore(detector=lambda: base().model_copy(update={"os": os_, "arch": arch}))


@pytest.fixture
def arm_linux_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import sys

    monkeypatch.setattr("athena.containers.runtime.shutil.which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr("athena.containers.service.list_containers", lambda rt: [])
    monkeypatch.setattr(
        apps_api, "compose", lambda runtime, name, path, *args: [sys.executable, "-c", "print(1)"]
    )
    with TestClient(make_app(tmp_path, store=_store_for("linux", "aarch64"))) as client:
        yield signed_in(client)


def test_store_marks_and_refuses_apps_for_another_cpu(arm_linux_api: TestClient) -> None:
    api = arm_linux_api
    by_id = {a["id"]: a for a in api.get("/api/store/apps").json()}
    assert by_id["handbrake"]["support"] == "unsupported"
    assert by_id["jellyfin"]["support"] == "native"

    detail = api.get("/api/store/apps/builtin/handbrake").json()
    assert detail["host_platform"] == "linux/arm64"
    assert detail["platforms"] == ["linux/amd64"]

    res = api.post("/api/store/apps/builtin/handbrake/install", json={"name": "hb"})
    assert res.status_code == 409
    assert "linux/arm64" in res.json()["detail"]
    assert api.get("/api/apps").json() == []


def test_store_allows_emulated_apps_on_an_arm_mac(tmp_path: Path, monkeypatch) -> None:
    import sys

    from test_apps import wait

    monkeypatch.setattr("athena.containers.runtime.shutil.which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr("athena.containers.service.list_containers", lambda rt: [])
    monkeypatch.setattr(
        apps_api, "compose", lambda runtime, name, path, *args: [sys.executable, "-c", "print(1)"]
    )
    with TestClient(make_app(tmp_path, store=_store_for("darwin", "arm64"))) as client:
        api = signed_in(client)
        hb = next(a for a in api.get("/api/store/apps").json() if a["id"] == "handbrake")
        assert hb["support"] == "emulated"
        res = api.post("/api/store/apps/builtin/handbrake/install", json={"name": "hb"})
        assert res.status_code == 202, res.text
        assert wait(api, res.json()["id"])["status"] == "succeeded"


def test_hex_secrets(tmp_path: Path) -> None:
    text, d = doc(
        [
            PORT,
            {"key": "IV", "label": "IV", "type": "password", "generate": "hex16"},
            {"key": "KEY", "label": "Key", "type": "password", "generate": "hex32"},
        ]
    )
    app = parse_app("a", "builtin", [("compose.yaml", text, d)])
    values = resolve_values(app.meta.env, {}, tmp_path)
    assert len(values["IV"]) == 32 and len(values["KEY"]) == 64
    int(values["IV"], 16), int(values["KEY"], 16)
    with pytest.raises(InstallValueError) as exc:
        resolve_values(app.meta.env, {"IV": "not-hex"}, tmp_path)
    assert "32 hexadecimal" in exc.value.errors["IV"]
    assert resolve_values(app.meta.env, {"IV": "a" * 32}, tmp_path)["IV"] == "a" * 32
