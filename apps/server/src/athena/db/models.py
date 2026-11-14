"""Database tables. Every change here needs an Alembic migration in db/migrations/versions;
tests/test_db.py fails if the models and migrations drift apart."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=64)
    password_hash: str
    is_admin: bool = True
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    appearance: str | None = None
    """The user's appearance settings as JSON (see athena.api.settings.Appearance)."""


class AuthSession(SQLModel, table=True):
    """A signed-in browser. Only a SHA-256 of the cookie token is stored."""

    __tablename__ = "sessions"

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True, max_length=64)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    csrf_token: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))


class AuditEntry(SQLModel, table=True):
    """Who did what to the host (docs/mvp-design.md §7). Never edited, only appended."""

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True), index=True)
    username: str = Field(max_length=64)
    action: str = Field(max_length=64, index=True)
    """Dotted verb, e.g. "container.stop", "runtime.start"."""
    target: str | None = Field(default=None, max_length=255)
    detail: str | None = None


class App(SQLModel, table=True):
    """An Athena-managed app: a compose project in <data-dir>/apps/<name>/compose.yaml."""

    __tablename__ = "apps"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=63)
    """Compose project name: lowercase letters, digits, dash and underscore."""
    source: str = Field(default="compose", max_length=16)
    """How it was created: "compose", "docker-run" or "catalog"."""
    catalog_id: str | None = Field(default=None, max_length=128)
    """For catalog installs: "<catalog>/<app id>", e.g. "builtin/jellyfin"."""
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))


class Catalog(SQLModel, table=True):
    """A remote app catalog, downloaded to <data-dir>/catalogs/<id>/."""

    __tablename__ = "catalogs"

    id: str = Field(primary_key=True, max_length=63)
    name: str = Field(max_length=100)
    url: str = Field(max_length=500)
    kind: str = Field(default="auto", max_length=16)
    """auto, athena or casaos."""
    app_count: int = 0
    refreshed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))


class SystemSetting(SQLModel, table=True):
    """Host-wide settings, one JSON value per key (see athena.system_settings)."""

    __tablename__ = "system_settings"

    key: str = Field(primary_key=True, max_length=64)
    value: str


class FileLocation(SQLModel, table=True):
    """A folder the file manager may browse (docs/mvp-design.md §4.3). Nothing outside
    the configured locations is reachable through the files API."""

    __tablename__ = "file_locations"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=64)
    path: str = Field(max_length=1024)
    """Absolute path on the host."""
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
