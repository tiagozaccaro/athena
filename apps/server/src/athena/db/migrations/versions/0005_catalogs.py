"""catalogs

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalogs",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(length=63), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("app_count", sa.Integer(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("catalogs")
