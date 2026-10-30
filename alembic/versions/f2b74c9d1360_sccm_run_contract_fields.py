"""Add README BRD SCCM deployment and reboot result fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b74c9d1360"
down_revision: str | Sequence[str] | None = "e7d9c2b1456a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "sccm_deployment_runs" in tables:
        columns = {item["name"] for item in inspector.get_columns("sccm_deployment_runs")}
        if "deployment_id" not in columns:
            op.add_column("sccm_deployment_runs", sa.Column("deployment_id", sa.String(length=100), nullable=True))
        indexes = {item["name"] for item in sa.inspect(bind).get_indexes("sccm_deployment_runs")}
        if "ix_sccm_deployment_runs_deployment_id" not in indexes:
            op.create_index("ix_sccm_deployment_runs_deployment_id", "sccm_deployment_runs", ["deployment_id"])
        if "sccm_deployments" in tables:
            op.execute(
                "UPDATE sccm_deployment_runs AS runs "
                "SET deployment_id = COALESCE(deployments.source_payload->>'id', runs.assignment_id) "
                "FROM sccm_deployments AS deployments "
                "WHERE runs.deployment_id IS NULL "
                "AND runs.assignment_id = deployments.assignment_id"
            )
    if "sccm_deployment_asset_details" in tables:
        columns = {item["name"] for item in sa.inspect(bind).get_columns("sccm_deployment_asset_details")}
        if "reboot_pending" not in columns:
            op.add_column("sccm_deployment_asset_details", sa.Column("reboot_pending", sa.Boolean(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "sccm_deployment_asset_details" in tables:
        columns = {item["name"] for item in inspector.get_columns("sccm_deployment_asset_details")}
        if "reboot_pending" in columns:
            op.drop_column("sccm_deployment_asset_details", "reboot_pending")
    if "sccm_deployment_runs" in tables:
        columns = {item["name"] for item in inspector.get_columns("sccm_deployment_runs")}
        if "deployment_id" in columns:
            indexes = {item["name"] for item in sa.inspect(bind).get_indexes("sccm_deployment_runs")}
            if "ix_sccm_deployment_runs_deployment_id" in indexes:
                op.drop_index("ix_sccm_deployment_runs_deployment_id", table_name="sccm_deployment_runs")
            op.drop_column("sccm_deployment_runs", "deployment_id")
