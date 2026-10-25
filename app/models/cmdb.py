
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CMDBServer(Base):
    """Server and operating-system configuration items."""

    __tablename__ = "cmdb_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_instance_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    ci_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    dns_host_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True, index=True
    )

    application_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    asset_owner: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    it_application_owner: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    system_environment: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    production_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    os_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    os_version: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    location: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    status: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    last_patch_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    source_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CMDBMiddleware(Base):
    """Middleware configuration items."""

    __tablename__ = "cmdb_middleware"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_instance_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    ci_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    server_instance_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    middleware_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    version: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    source_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CMDBDatabase(Base):
    """Database configuration items."""

    __tablename__ = "cmdb_databases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_instance_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    ci_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    server_instance_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    database_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    version: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    source_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CMDBRelationship(Base):
    """Relationships between CMDB configuration items."""

    __tablename__ = "cmdb_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_relationship_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    source_instance_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    destination_instance_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    relationship_type: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    source_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


Index(
    "ix_cmdb_servers_ip_status",
    CMDBServer.ip_address,
    CMDBServer.status,
)
