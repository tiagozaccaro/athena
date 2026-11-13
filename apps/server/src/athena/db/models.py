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
