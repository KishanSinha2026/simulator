"""Create Tenable scan and vulnerability tables.

Revision ID: 20261102_01
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261102_01"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "tenable_scans",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.Text()), sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(80)), sa.Column("result_type", sa.String(80)),
        sa.Column("start_time", sa.DateTime(timezone=True)),
        sa.Column("finish_time", sa.DateTime(timezone=True)),
        sa.Column("scan_duration", sa.Integer()), sa.Column("repository", sa.Text()),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "tenable_findings",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("source_finding_id", sa.String(160), nullable=False, unique=True),
        sa.Column("scan_id", sa.String(100), sa.ForeignKey("tenable_scans.id", ondelete="SET NULL"), index=True),
        sa.Column("plugin_id", sa.BigInteger(), index=True), sa.Column("plugin_name", sa.Text()),
        sa.Column("family", sa.Text()), sa.Column("severity", sa.String(40), index=True),
        sa.Column("ip_address", sa.String(64), index=True), sa.Column("dns_name", sa.Text()),
        sa.Column("host_id", sa.String(160), index=True), sa.Column("protocol", sa.String(32)),
        sa.Column("port", sa.Integer()), sa.Column("synopsis", sa.Text()),
        sa.Column("description", sa.Text()), sa.Column("plugin_output", sa.Text()),
        sa.Column("steps_to_remediate", sa.Text()), sa.Column("cvss_v2_base_score", sa.Float()),
        sa.Column("cvss_v3_base_score", sa.Float()), sa.Column("cvss_v4_base_score", sa.Float()),
        sa.Column("cve_ids", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("first_discovered", sa.DateTime(timezone=True)),
        sa.Column("last_observed", sa.DateTime(timezone=True)), sa.Column("repository", sa.Text()),
        sa.Column("status", sa.String(80)), sa.Column("exploit_available", sa.Boolean()),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_findings_actionable", "tenable_findings", ["severity", "last_observed"])

def downgrade():
    op.drop_index("ix_findings_actionable", table_name="tenable_findings")
    op.drop_table("tenable_findings")
    op.drop_table("tenable_scans")

