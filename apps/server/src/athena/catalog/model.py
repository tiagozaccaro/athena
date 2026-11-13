"""The catalog app format.

A catalog app is a plain compose file plus an `x-athena` block:

    x-athena:
      title: Jellyfin
      description: Stream your movies, shows and music.
      category: media
      icon: https://…/jellyfin.svg
      homepage: https://jellyfin.org
      web_port: WEB_PORT          # env key (or a number) that "Open" links to
      platforms: [linux/amd64, linux/arm64]
      env:                        # renders the install form; values go to .env
        - key: WEB_PORT
          label: Web port
          type: port
          default: "8096"
        - key: TZ
          label: Timezone
          default: "@timezone"    # tokens: @timezone @uid @gid @app_data[/sub]
        - key: DB_PASSWORD
          label: Database password
          type: password
          generate: secret        # filled with a random value if left empty

The compose file references values with standard `${KEY}` interpolation. Athena
writes the answers to `.env` next to `compose.yaml`, which compose reads on its own.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

FieldType = Literal["text", "password", "port", "path", "number", "boolean", "select"]
Category = Literal[
    "media",
    "files",
    "productivity",
    "development",
    "home",
    "network",
    "security",
    "monitoring",
    "downloads",
    "utilities",
]
CATEGORY_LABELS: dict[str, str] = {
    "media": "Media",
    "files": "Files & sync",
    "productivity": "Productivity",
    "development": "Development",
    "home": "Home automation",
    "network": "Network",
    "security": "Security",
    "monitoring": "Monitoring",
    "downloads": "Downloads",
    "utilities": "Utilities",
}

ENV_KEY = r"^[A-Z][A-Z0-9_]{0,63}$"
APP_ID = r"^[a-z0-9][a-z0-9-]{0,62}$"


class EnvField(BaseModel):
    key: str = Field(pattern=ENV_KEY)
    label: str
    description: str | None = None
    type: FieldType = "text"
    default: str | None = None
    """A literal, or a token: @timezone, @uid, @gid, @app_data, @app_data/<sub>."""
    required: bool = True
    options: list[str] | None = None
    """For type: select."""
    generate: Literal["secret"] | None = None
    """Fill an empty value with a random secret at install time."""
    advanced: bool = False
    """Collapsed in the install form."""

    @field_validator("options")
    @classmethod
    def options_need_select(cls, value: list[str] | None, info) -> list[str] | None:
        if value is not None and not value:
            raise ValueError("options can't be empty")
        return value


class AppMeta(BaseModel):
    title: str
    description: str
    category: Category
    icon: str | None = None
    homepage: str | None = None
    web_port: str | int | None = None
    """An env key holding the web port, or a fixed port number."""
    web_path: str = "/"
    platforms: list[str] = Field(default_factory=lambda: ["linux/amd64", "linux/arm64"])
    env: list[EnvField] = Field(default_factory=list)
    notes: str | None = None
    """Shown on the app page, e.g. first-login instructions."""


class CatalogApp(BaseModel):
    id: str = Field(pattern=APP_ID)
    catalog: str
    """Which catalog it came from ("builtin" or a remote catalog's id)."""
    meta: AppMeta
    compose: str
    images: list[str]


class InvalidCatalogAppError(ValueError):
    pass


_INTERP = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)")


def parse_app(app_id: str, catalog: str, compose_text: str, doc: dict[str, Any]) -> CatalogApp:
    """Build a CatalogApp from a parsed compose document, checking its metadata."""
    raw = doc.get("x-athena")
    if not isinstance(raw, dict):
        raise InvalidCatalogAppError(f"{app_id}: missing `x-athena` metadata")
    try:
        meta = AppMeta.model_validate(raw)
    except ValidationError as exc:
        raise InvalidCatalogAppError(f"{app_id}: invalid x-athena: {exc}") from exc

    keys = [f.key for f in meta.env]
    if len(keys) != len(set(keys)):
        raise InvalidCatalogAppError(f"{app_id}: duplicate env keys")
    for f in meta.env:
        if f.type == "select" and not f.options:
            raise InvalidCatalogAppError(f"{app_id}: {f.key} is a select without options")
    if isinstance(meta.web_port, str) and meta.web_port not in keys:
        raise InvalidCatalogAppError(f"{app_id}: web_port {meta.web_port} isn't an env key")

    # Every ${VAR} in the compose file must be an env field or provided by Athena.
    provided = {*keys, "ATHENA_APP_DATA"}
    unknown = sorted({m for m in _INTERP.findall(compose_text) if m not in provided})
    if unknown:
        raise InvalidCatalogAppError(f"{app_id}: undeclared variables {', '.join(unknown)}")

    services = doc.get("services") or {}
    images = sorted({s.get("image", "") for s in services.values() if isinstance(s, dict)} - {""})
    if not images:
        raise InvalidCatalogAppError(f"{app_id}: no images")
    return CatalogApp(id=app_id, catalog=catalog, meta=meta, compose=compose_text, images=images)
