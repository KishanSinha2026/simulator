"""Create synthetic BMC CMDB CI and IP endpoint tables.

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
        "cmdb_computer_systems",
        sa.Column("instance_id", sa.String(64), primary_key=True),
        sa.Column("dataset_id", sa.String(100), nullable=False),
        sa.Column("inventory_type", sa.String(32), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_cmdb_computer_systems_dataset_id", "cmdb_computer_systems", ["dataset_id"])
    op.create_index("ix_cmdb_ci_dataset_instance", "cmdb_computer_systems", ["dataset_id", "instance_id"])
    op.create_table(
        "cmdb_ip_endpoints",
        sa.Column("instance_id", sa.String(64), primary_key=True),
        sa.Column("dataset_id", sa.String(100), nullable=False),
        sa.Column("address", sa.String(64), nullable=False, unique=True),
        sa.Column("computer_system_instance_id", sa.String(64), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["computer_system_instance_id"], ["cmdb_computer_systems.instance_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_cmdb_ip_endpoints_dataset_id", "cmdb_ip_endpoints", ["dataset_id"])
    op.create_index("ix_cmdb_ip_endpoints_address", "cmdb_ip_endpoints", ["address"], unique=True)
    op.create_index("ix_cmdb_ip_endpoints_computer_system_instance_id", "cmdb_ip_endpoints", ["computer_system_instance_id"])

def downgrade():
    op.drop_table("cmdb_ip_endpoints")
    op.drop_table("cmdb_computer_systems")

