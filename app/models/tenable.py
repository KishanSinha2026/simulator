
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


class TenableScan(Base):
    """Tenable scan metadata."""

    __tablename__ = "tenable_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_scan_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )

    name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
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


class TenableFinding(Base):
    """A vulnerability finding returned by Tenable."""

    __tablename__ = "tenable_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_finding_id: Mapped[str | None] = mapped_column(
        String(150), nullable=True, unique=True
    )

    scan_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenable_scans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    plugin_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )

    plugin_name: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True, index=True
    )

    dns_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    host_id: Mapped[str | None] = mapped_column(
        String(150), nullable=True, index=True
    )

    severity: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    synopsis: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    plugin_output: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    steps_to_remediate: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    cvss_v3_base_score: Mapped[float | None] = mapped_column(
        nullable=True
    )

    cvss_v4_base_score: Mapped[float | None] = mapped_column(
        nullable=True
    )

    first_discovered: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_observed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    repository: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    protocol: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    port: Mapped[int | None] = mapped_column(
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

    scan: Mapped[TenableScan | None] = relationship()

    cves: Mapped[list["TenableFindingCVE"]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TenableFindingCVE(Base):
    """CVE identifiers associated with a Tenable finding."""

    __tablename__ = "tenable_finding_cves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    finding_id: Mapped[int] = mapped_column(
        ForeignKey("tenable_findings.id", ondelete="CASCADE"),
        nullable=False,
    )

    cve: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    finding: Mapped[TenableFinding] = relationship(
        back_populates="cves"
    )

    __table_args__ = (
        UniqueConstraint(
            "finding_id",
            "cve",
            name="uq_tenable_finding_cves_finding_id_cve",
        ),
    )


Index(
    "ix_tenable_findings_severity_last_observed",
    TenableFinding.severity,
    TenableFinding.last_observed,
)
