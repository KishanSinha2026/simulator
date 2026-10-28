
"""initial_schema

Revision ID: 357b1d2e550c
Revises: 
Create Date: 2026-10-26 15:26:07.544990
"""

from collections.abc import Sequence

from alembic import op

from app.db.base import Base
from app import models  # noqa: F401 - registers integration tables on Base.metadata



# Alembic revision identifiers
revision: str = '357b1d2e550c'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial VPM360 schema for all registered integrations."""
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Drop the schema created by this initial revision."""
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
