from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Scan(Base):
    __tablename__ = "tenable_scans"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(80))
    result_type: Mapped[str | None] = mapped_column(String(80))
    start_time: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    finish_time: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    scan_duration: Mapped[int | None] = mapped_column(Integer)
    repository: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Finding(Base):
    __tablename__ = "tenable_findings"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    source_finding_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    scan_id: Mapped[str | None] = mapped_column(ForeignKey("tenable_scans.id", ondelete="SET NULL"), index=True)
    plugin_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    plugin_name: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(40), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), index=True)
    dns_name: Mapped[str | None] = mapped_column(Text)
    host_id: Mapped[str | None] = mapped_column(String(160), index=True)
    protocol: Mapped[str | None] = mapped_column(String(32))
    port: Mapped[int | None] = mapped_column(Integer)
    synopsis: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    plugin_output: Mapped[str | None] = mapped_column(Text)
    steps_to_remediate: Mapped[str | None] = mapped_column(Text)
    cvss_v2_base_score: Mapped[float | None] = mapped_column(Float)
    cvss_v3_base_score: Mapped[float | None] = mapped_column(Float)
    cvss_v4_base_score: Mapped[float | None] = mapped_column(Float)
    cve_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    first_discovered: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    last_observed: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    repository: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(80))
    exploit_available: Mapped[bool | None] = mapped_column(Boolean)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

