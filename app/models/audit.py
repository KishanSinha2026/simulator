
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncRun(Base):
    """Tracks a data import or synchronization attempt."""

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    integration: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )

    provider: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="started"
    )

    records_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    records_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )


class MockRequestLog(Base):
    """Records simulated or live integration API requests."""

    __tablename__ = "mock_request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    integration: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    provider: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    method: Mapped[str] = mapped_column(
        String(10), nullable=False
    )

    endpoint: Mapped[str] = mapped_column(
        String(500), nullable=False
    )

    status_code: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )


Index(
    "ix_mock_request_logs_integration_created",
    MockRequestLog.integration,
    MockRequestLog.created_at,
)
