"""app catalog id

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("apps") as batch:
        batch.add_column(
            sa.Column("catalog_id", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("apps") as batch:
        batch.drop_column("catalog_id")
