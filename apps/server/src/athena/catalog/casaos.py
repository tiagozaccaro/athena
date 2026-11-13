"""Import CasaOS AppStore apps (Apache-2.0) into Athena's catalog format.

CasaOS apps live in `Apps/<Name>/docker-compose.yml` with an `x-casaos` block. They
assume CasaOS conventions that Athena maps like this:

    /DATA/AppData/$AppID[/…]   ->  ${ATHENA_APP_DATA}[/…]
    /DATA/<Folder>[/…]         ->  ${<FOLDER>_PATH}[/…]   (path field, default @app_data/<folder>)
    $PUID / $PGID / $TZ        ->  fields with @uid / @gid / @timezone defaults
    $AppID                     ->  the app id
    x-casaos.port_map          ->  WEB_PORT field, replacing the main service's published port
    any other $VAR             ->  a text field (passwords get `generate: secret`)
"""

import re
from pathlib import Path
from typing import Any

import yaml

from athena.catalog.model import CatalogApp, InvalidCatalogAppError, parse_app

CATEGORY_MAP = {
    "media": "media",
    "productivity": "productivity",
    "home": "home",
    "networking": "network",
    "network": "network",
    "utilities": "utilities",
    "developer": "development",
    "development": "development",
    "downloader": "downloads",
    "downloads": "downloads",
    "backup": "files",
    "cloud": "files",
    "file": "files",
    "security": "security",
    "monitoring": "monitoring",
}

_VAR = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)[^}]*\}|([A-Za-z_][A-Za-z0-9_]*))")
_DATA_FOLDER = re.compile(r"/DATA/(?!AppData/)([A-Za-z0-9_-]+)")
_APPDATA = re.compile(r"/DATA/AppData/(?:\$\{AppID\}|\$AppID)")
_SECRETISH = re.compile(r"(PASS|PWD|SECRET|TOKEN|KEY)", re.IGNORECASE)


class _Yaml12Loader(yaml.SafeLoader):
    """Like compose (YAML 1.2): only true/false are booleans; yes/no/on/off stay strings."""


_Yaml12Loader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)


def _text(value: Any) -> str:
    """CasaOS strings are often {en_US: …, zh_CN: …} maps."""
    if isinstance(value, dict):
        for lang in ("en_US", "en_GB", "en"):
            if value.get(lang):
                return str(value[lang]).strip()
        return str(next(iter(value.values()), "")).strip()
    return str(value or "").strip()


def app_id_for(folder_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", folder_name.lower()).strip("-")[:63] or "app"


class _Converter:
    def __init__(self, app_id: str) -> None:
        self.app_id = app_id
        self.fields: dict[str, dict[str, Any]] = {}

    def field(self, key: str, **spec: Any) -> str:
        self.fields.setdefault(key, {"key": key, **spec})
        return "${" + key + "}"

    def _var(self, name: str) -> str:
        if name == "AppID":
            return self.app_id
        if name == "PUID":
            return self.field("PUID", label="User ID", default="@uid", advanced=True)
        if name == "PGID":
            return self.field("PGID", label="Group ID", default="@gid", advanced=True)
        if name == "TZ":
            return self.field("TZ", label="Timezone", default="@timezone", advanced=True)
        key = re.sub(r"[^A-Z0-9_]", "_", name.upper())
        if not re.match(r"^[A-Z]", key):
            key = f"V_{key}"
        if _SECRETISH.search(name):
            return self.field(key, label=name, type="password", generate="secret")
        return self.field(key, label=name, required=False)

    def string(self, value: str) -> str:
        value = _APPDATA.sub("${ATHENA_APP_DATA}", value)

        def folder(match: re.Match[str]) -> str:
            name = match.group(1)
            key = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") + "_PATH"
            return self.field(
                key,
                label=f"{name} folder",
                type="path",
                default=f"@app_data/{name.lower()}",
                description=f"The CasaOS {name} folder.",
            )

        value = _DATA_FOLDER.sub(folder, value)
        parts: list[str] = []
        last = 0
        for m in _VAR.finditer(value):
            start = m.start()
            if start > 0 and value[start - 1] == "$":  # "$$" escape: keep literally
                continue
            parts.append(value[last:start])
            name = m.group(1) or m.group(2)
            parts.append(
                m.group(0)
                if name == "ATHENA_APP_DATA" or name in self._declared()
                else self._var(name)
            )
            last = m.end()
        parts.append(value[last:])
        return "".join(parts)

    def _declared(self) -> set[str]:
        return set(self.fields)

    def walk(self, node: Any) -> Any:
        if isinstance(node, str):
            return self.string(node)
        if isinstance(node, list):
            return [self.walk(v) for v in node]
        if isinstance(node, dict):
            return {k: self.walk(v) for k, v in node.items() if k != "x-casaos"}
        return node


def _web_port(services: dict[str, Any], main: str | None, port_map: str) -> bool:
    """Replace the main service's published `port_map` with ${WEB_PORT}. True if done."""
    candidates = [services[main]] if main in services else list(services.values())
    for service in candidates:
        ports = service.get("ports") or []
        for i, port in enumerate(ports):
            if isinstance(port, dict) and str(port.get("published", "")) == port_map:
                port["published"] = "${WEB_PORT}"
                return True
            if isinstance(port, str | int):
                text = str(port)
                head, sep, tail = text.rpartition(":")
                host_part = head.rsplit(":", 1)[-1] if sep else ""
                if sep and host_part == port_map:
                    prefix = head[: len(head) - len(host_part)]
                    ports[i] = f"{prefix}${{WEB_PORT}}:{tail}"
                    return True
    return False


def convert(folder_name: str, compose_text: str, catalog: str) -> CatalogApp:
    """Convert one CasaOS docker-compose.yml into a CatalogApp. Raises InvalidCatalogAppError."""
    try:
        doc = yaml.load(compose_text, Loader=_Yaml12Loader)  # a SafeLoader subclass
    except yaml.YAMLError as exc:
        raise InvalidCatalogAppError(f"{folder_name}: invalid YAML: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("services"), dict):
        raise InvalidCatalogAppError(f"{folder_name}: no services")
    meta = doc.get("x-casaos") or {}
    app_id = app_id_for(folder_name)
    conv = _Converter(app_id)

    services = conv.walk(doc["services"])
    port_map = str(meta.get("port_map") or "").strip()
    web_port: str | int | None = None
    if port_map.isdigit():
        if _web_port(services, meta.get("main"), port_map):
            conv.field("WEB_PORT", label="Web port", type="port", default=port_map)
            web_port = "WEB_PORT"
        else:
            web_port = int(port_map)

    title = _text(meta.get("title")) or folder_name
    tagline = _text(meta.get("tagline")) or _text(meta.get("description")).split("\n")[0]
    tips = meta.get("tips") or {}
    notes = _text(tips.get("before_install")) if isinstance(tips, dict) else ""
    archs = meta.get("architectures") or ["amd64", "arm64"]
    category = CATEGORY_MAP.get(_text(meta.get("category")).lower(), "utilities")

    athena_meta: dict[str, Any] = {
        "title": title,
        "description": tagline[:300] or title,
        "category": category,
        "icon": meta.get("icon") or None,
        "homepage": meta.get("website") or meta.get("repo") or meta.get("developer") or None,
        "web_port": web_port,
        "web_path": str(meta.get("index") or "/"),
        "platforms": [f"linux/{a}" for a in archs if isinstance(a, str)],
        "notes": (notes[:1000] or None),
        # Web port first, then the rest in the order they appear in the file.
        "env": sorted(conv.fields.values(), key=lambda f: f["key"] != "WEB_PORT"),
    }
    if athena_meta["homepage"] and not str(athena_meta["homepage"]).startswith("http"):
        athena_meta["homepage"] = None

    out: dict[str, Any] = {"x-athena": athena_meta, "services": services}
    for key in ("volumes", "networks", "secrets", "configs"):
        if key in doc:
            out[key] = conv.walk(doc[key])
    text = (
        f"# Imported from the CasaOS AppStore (Apache-2.0): Apps/{folder_name}\n"
        + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=100)
    )
    parsed = yaml.safe_load(text)
    return parse_app(app_id, catalog, text, parsed)


def import_casaos_tree(source: Path, dest: Path, catalog: str) -> tuple[int, list[str]]:
    """Convert each `Apps/*/docker-compose.yml` under `source` to `dest/apps/<id>/compose.yaml`."""
    apps_dir = source / "Apps"
    if not apps_dir.is_dir():
        raise InvalidCatalogAppError("Not a CasaOS AppStore: no Apps/ folder")
    count, errors = 0, []
    for compose_file in sorted(apps_dir.glob("*/docker-compose.yml")):
        name = compose_file.parent.name
        try:
            app = convert(name, compose_file.read_text(encoding="utf-8"), catalog)
        except (InvalidCatalogAppError, OSError) as exc:
            errors.append(str(exc))
            continue
        target = dest / "apps" / app.id
        target.mkdir(parents=True, exist_ok=True)
        (target / "compose.yaml").write_text(app.compose, encoding="utf-8")
        count += 1
    return count, errors
