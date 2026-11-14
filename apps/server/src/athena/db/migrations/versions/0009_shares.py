"""share links

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shares",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("path", sqlmodel.sql.sqltypes.AutoString(length=4096), nullable=False),
        sa.Column("mode", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("downloads", sa.Integer(), nullable=False),
        sa.Column("uploads", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["file_locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shares_location_id"), "shares", ["location_id"], unique=False)
    op.create_index(op.f("ix_shares_token"), "shares", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_shares_token"), table_name="shares")
    op.drop_index(op.f("ix_shares_location_id"), table_name="shares")
    op.drop_table("shares")
