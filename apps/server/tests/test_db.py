from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlmodel import SQLModel

import athena.db.models  # noqa: F401
from athena.db import Database


def test_migrations_create_the_schema(tmp_path: Path) -> None:
    db = Database(tmp_path / "athena.db")
    db.migrate()
    assert {"users", "sessions", "alembic_version"} <= set(inspect(db.engine).get_table_names())


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "athena.db")
    db.migrate()
    db.migrate()


def test_models_match_migrations(tmp_path: Path) -> None:
    """Fails when a model changes without a matching Alembic migration."""
    db = Database(tmp_path / "athena.db")
    db.migrate()
    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    assert diff == [], f"models and migrations differ; add a migration: {diff}"
