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
    """How it was created: "compose", "docker-run" (later: "catalog")."""
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
