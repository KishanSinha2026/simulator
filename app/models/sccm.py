"""SQLAlchemy models for SCCM 2509 Windows execution and deployment tracking."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SCCMDevice(Base):
    """Configuration Manager managed device / resource matching BRD Table 20."""

    __tablename__ = "sccm_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    resource_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True, index=True
    )

    operating_system: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    client_active_status: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    is_client: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    last_active_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    collection_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
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


class SCCMCollection(Base):
    """Configuration Manager device collection matching BRD Table 20."""

    __tablename__ = "sccm_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    collection_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    comment: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    member_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
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


class SCCMDeployment(Base):
    """Configuration Manager software update group deployment policy."""

    __tablename__ = "sccm_deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    assignment_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    target_collection_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )

    reboot_policy: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    window_end: Mapped[datetime | None] = mapped_column(
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


class SCCMDeploymentRun(Base):
    """Guarded patch deployment execution run matching BRD Section 8.5.5."""

    __tablename__ = "sccm_deployment_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    run_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    change_number: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )

    mode: Mapped[str] = mapped_column(
        String(100), nullable=False, default="STANDARD_PATCH"
    )

    target_collection_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )

    assignment_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )

    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reboot_policy: Mapped[str] = mapped_column(
        String(100), nullable=False, default="CLIENT_APPROVED"
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="in_progress", index=True
    )

    compliant_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    in_progress_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    unknown_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    skipped_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
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

    asset_details: Mapped[list["SCCMDeploymentAssetDetail"]] = relationship(
        back_populates="deployment_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SCCMDeploymentAssetDetail(Base):
    """Per-device deployment status and compliance outcome matching BRD Section 4.6 & 8.5.5."""

    __tablename__ = "sccm_deployment_asset_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    deployment_run_id: Mapped[int] = mapped_column(
        ForeignKey("sccm_deployment_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )

    server_ci_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    hostname: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Compliant", index=True
    )

    status_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    error_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    status_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    source_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    deployment_run: Mapped["SCCMDeploymentRun"] = relationship(
        back_populates="asset_details"
    )
