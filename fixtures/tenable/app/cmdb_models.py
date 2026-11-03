from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class CMDBBase(DeclarativeBase):
    pass

class ComputerSystem(CMDBBase):
    __tablename__ = "cmdb_computer_systems"
    instance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    inventory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False)

class IPEndpoint(CMDBBase):
    __tablename__ = "cmdb_ip_endpoints"
    instance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    computer_system_instance_id: Mapped[str] = mapped_column(
        ForeignKey("cmdb_computer_systems.instance_id", ondelete="CASCADE"), nullable=False, index=True)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False)

Index("ix_cmdb_ci_dataset_instance", ComputerSystem.dataset_id, ComputerSystem.instance_id)

