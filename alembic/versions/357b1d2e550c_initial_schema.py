
"""initial_schema

Revision ID: 357b1d2e550c
Revises: 
Create Date: 2026-10-26 15:26:07.544990
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa



# Alembic revision identifiers
revision: str = '357b1d2e550c'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this schema change."""
    pass


def downgrade() -> None:
    """Reverse this schema change when safe."""
    pass
