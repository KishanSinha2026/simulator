"""Add BRD governance lifecycle and evidence persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d14c7a90b2e1"
down_revision: str | Sequence[str] | None = "9b6f1c4e8a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patch_governance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_record_id", sa.String(150), nullable=False, unique=True),
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("tenable_findings.id", ondelete="SET NULL")),
        sa.Column("squad1_vulnerability_id", sa.Integer(), sa.ForeignKey("squad1_vulnerabilities.id", ondelete="SET NULL")),
        sa.Column("cmdb_instance_id", sa.String(255)),
        sa.Column("change_id", sa.Integer(), sa.ForeignKey("itsm_changes.id", ondelete="SET NULL")),
        sa.Column("host_name", sa.String(255)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("current_stage", sa.String(100)),
        sa.Column("current_responsible_party", sa.String(255)),
        sa.Column("overall_governance_status", sa.String(100)),
        sa.Column("blocker_flag", sa.Boolean()),
        sa.Column("brd_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_patch_governance_records_cmdb_instance_id", "patch_governance_records", ["cmdb_instance_id"])
    op.create_index("ix_patch_governance_records_host_name", "patch_governance_records", ["host_name"])
    op.create_index("ix_patch_governance_records_ip_address", "patch_governance_records", ["ip_address"])
    op.create_index("ix_patch_governance_records_current_stage", "patch_governance_records", ["current_stage"])
    op.create_index("ix_patch_governance_records_overall_governance_status", "patch_governance_records", ["overall_governance_status"])
    op.create_index("ix_patch_governance_cmdb_stage", "patch_governance_records", ["cmdb_instance_id", "current_stage"])

    op.create_table(
        "evidence_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("governance_record_id", sa.Integer(), sa.ForeignKey("patch_governance_records.id", ondelete="SET NULL")),
        sa.Column("integration", sa.String(50), nullable=False),
        sa.Column("evidence_type", sa.String(100), nullable=False),
        sa.Column("reference_id", sa.String(255)),
        sa.Column("storage_uri", sa.Text()),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("captured_by", sa.String(255)),
        sa.Column("retention_class", sa.String(100)),
    )
    op.create_index("ix_evidence_artifacts_governance_record_id", "evidence_artifacts", ["governance_record_id"])
    op.create_index("ix_evidence_artifacts_integration", "evidence_artifacts", ["integration"])
    op.create_index("ix_evidence_artifacts_reference_id", "evidence_artifacts", ["reference_id"])


def downgrade() -> None:
    op.drop_table("evidence_artifacts")
    op.drop_table("patch_governance_records")
