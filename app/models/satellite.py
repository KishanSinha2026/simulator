
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SatelliteHost(Base):
    """Host registered in Red Hat Satellite."""

    __tablename__ = "satellite_hosts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_host_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
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

    organization_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    location_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
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


class SatelliteJobTemplate(Base):
    """Job template available in Satellite."""

    __tablename__ = "satellite_job_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_template_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )

    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    template_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    input_schema: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    source_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SatelliteJobRun(Base):
    """A simulated or real Satellite job invocation."""

    __tablename__ = "satellite_job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_invocation_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )

    template_id: Mapped[int] = mapped_column(
        ForeignKey(
            "satellite_job_templates.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )

    inputs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
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

    template: Mapped[SatelliteJobTemplate] = relationship()

    host_results: Mapped[list["SatelliteJobHostResult"]] = relationship(
        back_populates="job_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SatelliteJobHostResult(Base):
    """Result of a job invocation for an individual host."""

    __tablename__ = "satellite_job_host_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    job_run_id: Mapped[int] = mapped_column(
        ForeignKey("satellite_job_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    host_id: Mapped[int] = mapped_column(
        ForeignKey("satellite_hosts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )

    result_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    source_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job_run: Mapped[SatelliteJobRun] = relationship(
        back_populates="host_results"
    )

    host: Mapped[SatelliteHost] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "job_run_id",
            "host_id",
            name="uq_satellite_job_host_results_run_host",
        ),
    )


Index(
    "ix_satellite_job_runs_status_created",
    SatelliteJobRun.status,
    SatelliteJobRun.created_at,
)
