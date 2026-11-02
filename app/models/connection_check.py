"""Durable history for connector test-connection attempts."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IntegrationConnectionCheck(Base):
    """One sanitized result for each manual or automated connector probe."""

    __tablename__ = "integration_connection_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    connected: Mapped[bool] = mapped_column(nullable=False)
    healthy: Mapped[bool] = mapped_column(nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


Index(
    "ix_integration_connection_checks_integration_checked_at",
    IntegrationConnectionCheck.integration,
    IntegrationConnectionCheck.checked_at,
)
