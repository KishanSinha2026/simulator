"""SQLAlchemy models for Squad1 vulnerability lifecycle tracking."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Squad1Vulnerability(Base):
    """Squad1 vulnerability lifecycle record matching BRD Section 4.2 & Table 59."""

    __tablename__ = "squad1_vulnerabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    vulnerability_no: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    plugin_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )

    target: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    vulnerability_name: Mapped[str] = mapped_column(
        String(500), nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    protocol: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    port: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    risk_rating: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    status: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    recommendation: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    solution_category: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    plugin_output: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    owasp_mapping: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    cve_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    cvss_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    risk_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    vulnerability_holder: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    vulnerability_holder_department: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    vulnerability_holder_location: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    bu_head: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    report_published_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    planned_remediation_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ageing: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    risk_severity_change_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    exception_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    exception_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    exception_status: Mapped[str | None] = mapped_column(
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

    __table_args__ = (
        Index("ix_squad1_vulnerabilities_target_status", "target", "status"),
        Index("ix_squad1_vulnerabilities_exception", "exception_id", "exception_end_date"),
    )
