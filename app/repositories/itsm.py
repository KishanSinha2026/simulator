"""Database repositories for BMC Helix ITSM resources."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.itsm import (
    ITSMChange,
    ITSMChangeHistory,
    ITSMWorklog,
)
from app.repositories.base import BaseRepository


class ITSMChangeRepository(BaseRepository[ITSMChange]):
    """Database operations for ITSM change requests."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, ITSMChange)

    def get_by_source_id(
        self,
        source_change_id: str,
    ) -> ITSMChange | None:
        """Find a change using its external ITSM identifier."""
        statement = select(ITSMChange).where(
            ITSMChange.source_change_id == source_change_id
        )
        return self.db.scalars(statement).first()

    def list_by_status(
        self,
        status: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ITSMChange]:
        """Return changes matching a status."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        statement = (
            select(ITSMChange)
            .where(ITSMChange.status == status)
            .order_by(ITSMChange.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class ITSMWorklogRepository(BaseRepository[ITSMWorklog]):
    """Database operations for ITSM worklogs."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, ITSMWorklog)

    def get_by_source_id(
        self,
        source_worklog_id: str,
    ) -> ITSMWorklog | None:
        """Find a worklog using its external source identifier."""
        statement = select(ITSMWorklog).where(
            ITSMWorklog.source_worklog_id == source_worklog_id
        )
        return self.db.scalars(statement).first()

    def list_by_change_id(
        self,
        change_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ITSMWorklog]:
        """Return worklogs associated with a database change ID."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        statement = (
            select(ITSMWorklog)
            .where(ITSMWorklog.change_id == change_id)
            .order_by(ITSMWorklog.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class ITSMChangeHistoryRepository(
    BaseRepository[ITSMChangeHistory]
):
    """Database operations for ITSM change history."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, ITSMChangeHistory)

    def list_by_change_id(
        self,
        change_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ITSMChangeHistory]:
        """Return history records associated with a database change ID."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        statement = (
            select(ITSMChangeHistory)
            .where(ITSMChangeHistory.change_id == change_id)
            .order_by(ITSMChangeHistory.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())