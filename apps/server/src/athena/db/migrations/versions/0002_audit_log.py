"""audit log

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("action", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("target", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("detail", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_log") as batch:
        batch.create_index(batch.f("ix_audit_log_at"), ["at"], unique=False)
        batch.create_index(batch.f("ix_audit_log_action"), ["action"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_log")
