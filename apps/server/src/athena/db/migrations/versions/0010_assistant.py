"""AI providers and conversations

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("config", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("secrets", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ai_conversations",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("provider_id", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("history", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_conversations_user_id"), "ai_conversations", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_ai_conversations_updated_at"), "ai_conversations", ["updated_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_conversations_updated_at"), table_name="ai_conversations")
    op.drop_index(op.f("ix_ai_conversations_user_id"), table_name="ai_conversations")
    op.drop_table("ai_conversations")
    op.drop_table("ai_providers")
