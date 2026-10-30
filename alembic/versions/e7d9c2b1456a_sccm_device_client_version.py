"""Add SCCM client version as a normalized device field."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7d9c2b1456a"
down_revision: str | Sequence[str] | None = "c1a9d8402f7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sccm_devices" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("sccm_devices")}
    if "client_version" not in columns:
        op.add_column("sccm_devices", sa.Column("client_version", sa.String(length=100), nullable=True))
    op.execute(
        "UPDATE sccm_devices "
        "SET client_version = source_payload->>'client_version' "
        "WHERE client_version IS NULL AND source_payload ? 'client_version'"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sccm_devices" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("sccm_devices")}
    if "client_version" in columns:
        op.drop_column("sccm_devices", "client_version")
