"""Persisted Ansible Automation Platform job executions."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnsibleJobRun(Base):
    """A remote AWX/AAP job and its latest known state."""

    __tablename__ = "ansible_job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_job_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    job_template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    limit: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_vars: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


Index("ix_ansible_job_runs_status_created", AnsibleJobRun.status, AnsibleJobRun.created_at)
