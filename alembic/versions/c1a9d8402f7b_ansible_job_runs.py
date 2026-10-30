"""Add persisted Ansible Automation Platform job runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1a9d8402f7b"
down_revision: str | Sequence[str] | None = "a74c2e6105f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "ansible_job_runs" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "ansible_job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_job_id", sa.String(100), nullable=False, unique=True),
        sa.Column("job_template_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("limit", sa.Text(), nullable=True),
        sa.Column("extra_vars", sa.JSON(), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ansible_job_runs_status_created", "ansible_job_runs", ["status", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if "ansible_job_runs" not in sa.inspect(bind).get_table_names():
        return
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("ansible_job_runs")}
    if "ix_ansible_job_runs_status_created" in indexes:
        op.drop_index("ix_ansible_job_runs_status_created", table_name="ansible_job_runs")
    op.drop_table("ansible_job_runs")
