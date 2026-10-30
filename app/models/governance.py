"""Persisted BRD governance lifecycle records and supporting evidence."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PatchGovernanceRecord(Base):
    """One finding/asset/change lifecycle row for the BRD governance pack.

    ``brd_fields`` retains the exact 73 BRD labels and values. Stable linkage
    fields are columns so reports and reconciliation can query the lifecycle.
    """

    __tablename__ = "patch_governance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_record_id: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("tenable_findings.id", ondelete="SET NULL"), nullable=True)
    squad1_vulnerability_id: Mapped[int | None] = mapped_column(ForeignKey("squad1_vulnerabilities.id", ondelete="SET NULL"), nullable=True)
    cmdb_instance_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    change_id: Mapped[int | None] = mapped_column(ForeignKey("itsm_changes.id", ondelete="SET NULL"), nullable=True)
    host_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    current_stage: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    current_responsible_party: Mapped[str | None] = mapped_column(String(255), nullable=True)
    overall_governance_status: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    blocker_flag: Mapped[bool | None] = mapped_column(nullable=True)
    brd_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EvidenceArtifact(Base):
    """Evidence metadata and payload/reference attached to a lifecycle record."""

    __tablename__ = "evidence_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    governance_record_id: Mapped[int | None] = mapped_column(ForeignKey("patch_governance_records.id", ondelete="SET NULL"), nullable=True, index=True)
    integration: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    captured_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retention_class: Mapped[str | None] = mapped_column(String(100), nullable=True)


Index("ix_patch_governance_cmdb_stage", PatchGovernanceRecord.cmdb_instance_id, PatchGovernanceRecord.current_stage)
