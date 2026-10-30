"""Make the BRD reboot_pending result a required boolean."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b6f1c4e8a20"
down_revision: str | Sequence[str] | None = "f2b74c9d1360"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sccm_deployment_asset_details" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("sccm_deployment_asset_details")}
    if "reboot_pending" not in columns:
        op.add_column(
            "sccm_deployment_asset_details",
            sa.Column("reboot_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        return
    op.execute("UPDATE sccm_deployment_asset_details SET reboot_pending = FALSE WHERE reboot_pending IS NULL")
    op.alter_column(
        "sccm_deployment_asset_details",
        "reboot_pending",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sccm_deployment_asset_details" not in inspector.get_table_names():
        return
    columns = {item["name"] for item in inspector.get_columns("sccm_deployment_asset_details")}
    if "reboot_pending" in columns:
        op.alter_column(
            "sccm_deployment_asset_details",
            "reboot_pending",
            existing_type=sa.Boolean(),
            nullable=True,
            server_default=None,
        )
