"""Persist Ansible Automation Platform job templates."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4f6a8b0c2d4"
down_revision: str | Sequence[str] | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "ansible_job_templates" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "ansible_job_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_template_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ansible_job_templates_name", "ansible_job_templates", ["name"])


def downgrade() -> None:
    bind = op.get_bind()
    if "ansible_job_templates" not in sa.inspect(bind).get_table_names():
        return
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("ansible_job_templates")}
    if "ix_ansible_job_templates_name" in indexes:
        op.drop_index("ix_ansible_job_templates_name", table_name="ansible_job_templates")
    op.drop_table("ansible_job_templates")
