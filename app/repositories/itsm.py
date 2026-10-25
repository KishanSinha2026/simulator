"""Database repository for BMC Helix ITSM changes and worklogs."""

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

    def get_by_source_id(self, source_id: str) -> ITSMChange | None:
        """Find a change using its external ITSM identifier."""
        statement = select(ITSMChange).where(
            ITSMChange.source_id == source_id
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
        statement = (
            select(ITSMChange)
            .where(ITSMChange.status == status)
            .order_by(ITSMChange.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class ITSMWorklogRepository(BaseRepository[ITSMWorklog]):
    """Database operations for ITSM worklog entries."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, ITSMWorklog)

    def list_by_change_id(
        self,
        change_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ITSMWorklog]:
        """Return worklogs associated with an external change ID."""
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
        change_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ITSMChangeHistory]:
        """Return history records for an external change ID."""
        statement = (
            select(ITSMChangeHistory)
            .where(ITSMChangeHistory.change_id == change_id)
            .order_by(ITSMChangeHistory.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())