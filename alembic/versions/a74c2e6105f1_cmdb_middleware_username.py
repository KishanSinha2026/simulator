"""Add BRD middleware Username field.

Revision ID: a74c2e6105f1
Revises: 357b1d2e550c
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a74c2e6105f1"
down_revision: str | Sequence[str] | None = "357b1d2e550c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Username when upgrading a database created before this field."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cmdb_middleware" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("cmdb_middleware")}
    if "username" not in columns:
        op.add_column("cmdb_middleware", sa.Column("username", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove the optional Username column when it exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cmdb_middleware" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("cmdb_middleware")}
    if "username" in columns:
        op.drop_column("cmdb_middleware", "username")
