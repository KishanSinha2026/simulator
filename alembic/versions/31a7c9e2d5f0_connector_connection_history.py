"""Persist connector connection test history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "31a7c9e2d5f0"
down_revision: str | Sequence[str] | None = "e4f6a8b0c2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_connection_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("integration", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("connected", sa.Boolean(), nullable=False),
        sa.Column("healthy", sa.Boolean(), nullable=False),
        sa.Column("provider_mode", sa.String(length=20), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_integration_connection_checks_integration_checked_at",
        "integration_connection_checks",
        ["integration", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integration_connection_checks_integration_checked_at",
        table_name="integration_connection_checks",
    )
    op.drop_table("integration_connection_checks")
