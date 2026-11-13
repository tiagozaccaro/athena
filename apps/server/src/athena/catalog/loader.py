"""Loads catalogs from disk and resolves install values."""

import logging
import os
import secrets
import time
from pathlib import Path

import yaml

from athena.apps.store import InvalidComposeError, parse_compose
from athena.catalog.model import CatalogApp, EnvField, InvalidCatalogAppError, parse_app

log = logging.getLogger(__name__)


def builtin_catalog_dir() -> Path | None:
    """The bundled catalog in the wheel, or the repo's catalog/ in development."""
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[1] / "catalog_builtin",  # athena/catalog_builtin (wheel)
        here.parents[5] / "catalog",  # repo root: apps/server/src/athena/catalog/loader.py
    ):
        if (candidate / "apps").is_dir():
            return candidate
    return None


def load_catalog(root: Path, catalog_id: str) -> tuple[list[CatalogApp], list[str]]:
    """All valid apps in `root/apps/*/compose.yaml`, plus error messages for invalid ones."""
    apps: list[CatalogApp] = []
    errors: list[str] = []
    for compose_file in sorted((root / "apps").glob("*/compose.yaml")):
        app_id = compose_file.parent.name
        try:
            text = compose_file.read_text(encoding="utf-8")
            doc = parse_compose(text)
            apps.append(parse_app(app_id, catalog_id, text, doc))
        except (OSError, InvalidComposeError, InvalidCatalogAppError, yaml.YAMLError) as exc:
            errors.append(f"{app_id}: {exc}")
    for message in errors:
        log.warning("catalog %s: skipped %s", catalog_id, message)
    return apps, errors


# ---------------------------------------------------------------- install values


class InstallValueError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def host_timezone() -> str:
    tz = os.environ.get("TZ")
    if tz:
        return tz
    localtime = Path("/etc/localtime")
    try:
        if localtime.is_symlink():
            target = str(localtime.resolve())
            if "zoneinfo/" in target:
                return target.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    return time.tzname[0] if time.tzname[0] and "/" in time.tzname[0] else "UTC"


def resolve_default(field: EnvField, app_data: Path) -> str:
    """Turn a field's default (literal or @token) into a concrete value."""
    default = field.default or ""
    if default == "@timezone":
        return host_timezone()
    if default in ("@uid", "@gid"):
        getter = getattr(os, "getuid" if default == "@uid" else "getgid", None)
        uid = getter() if getter else 1000
        # Root (the Linux service) would make app files root-owned; use the usual first user.
        return str(uid if uid != 0 else 1000)
    if default == "@app_data" or default.startswith("@app_data/"):
        sub = default.removeprefix("@app_data").lstrip("/")
        return str(app_data / sub) if sub else str(app_data)
    return default


def form_defaults(app: CatalogApp, app_data: Path) -> dict[str, str]:
    return {f.key: resolve_default(f, app_data) for f in app.meta.env}


def resolve_values(app: CatalogApp, submitted: dict[str, str], app_data: Path) -> dict[str, str]:
    """Validate submitted install values, fill defaults and secrets. Raises InstallValueError."""
    values: dict[str, str] = {}
    errors: dict[str, str] = {}
    for field in app.meta.env:
        raw = submitted.get(field.key)
        value = (raw if raw is not None else resolve_default(field, app_data)).strip()
        if not value and field.generate == "secret":
            value = secrets.token_urlsafe(24)
        if not value:
            if field.required:
                errors[field.key] = "Required"
            values[field.key] = ""
            continue
        if "\n" in value or "\r" in value:
            errors[field.key] = "Must be a single line"
        elif field.type == "port":
            if not value.isdigit() or not 1 <= int(value) <= 65535:
                errors[field.key] = "Must be a port number between 1 and 65535"
        elif field.type == "number":
            try:
                float(value)
            except ValueError:
                errors[field.key] = "Must be a number"
        elif field.type == "boolean":
            if value.lower() not in ("true", "false"):
                errors[field.key] = "Must be true or false"
            value = value.lower()
        elif field.type == "select":
            if value not in (field.options or []):
                errors[field.key] = f"Must be one of: {', '.join(field.options or [])}"
        elif field.type == "path" and not (
            value.startswith("/") or (len(value) > 2 and value[1] == ":")
        ):
            errors[field.key] = "Must be an absolute path"
        values[field.key] = value
    if errors:
        raise InstallValueError(errors)
    return values


def env_file(values: dict[str, str]) -> str:
    """Render a compose .env file.

    Single quotes are literal in compose .env files (no `$` interpolation), so they're
    used whenever possible; values containing a single quote fall back to double
    quotes with escapes.
    """
    lines = ["# Written by Athena from the install form. Edit and redeploy to change."]
    for key, value in values.items():
        if "'" not in value:
            lines.append(f"{key}='{value}'")
        else:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
            lines.append(f'{key}="{escaped}"')
    return "\n".join(lines) + "\n"
