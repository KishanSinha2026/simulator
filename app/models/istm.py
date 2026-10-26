"""SQLAlchemy models for BMC Helix ITSM changes and worklogs."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ITSMChange(Base):
    """BMC Helix ITSM change request."""

    __tablename__ = "itsm_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source_change_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    impact: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    urgency: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    location_company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    detailed_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    support_organization: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    support_group_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    change_nature: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    nature_of_change: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    application_infrastructure: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    downtime_required: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    service_ci: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    environment: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    scheduled_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    scheduled_end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
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

    worklogs: Mapped[list["ITSMWorklog"]] = relationship(
        back_populates="change",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    history: Mapped[list["ITSMChangeHistory"]] = relationship(
        back_populates="change",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ITSMWorklog(Base):
    """Worklog entries associated with a change request."""

    __tablename__ = "itsm_worklogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    change_id: Mapped[int] = mapped_column(
        ForeignKey("itsm_changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_worklog_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
    )
    worklog_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    submitter: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    source_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    change: Mapped[ITSMChange] = relationship(
        back_populates="worklogs",
    )


class ITSMChangeHistory(Base):
    """Audit trail for simulated change request updates."""

    __tablename__ = "itsm_change_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    change_id: Mapped[int] = mapped_column(
        ForeignKey("itsm_changes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    previous_status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    new_status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    change: Mapped[ITSMChange] = relationship(
        back_populates="history",
    )


Index(
    "ix_itsm_changes_status_created",
    ITSMChange.status,
    ITSMChange.created_at,
)