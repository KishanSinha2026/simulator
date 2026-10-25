"""Database repositories for integration audit records."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import MockRequestLog, SyncRun
from app.repositories.base import BaseRepository


class SyncRunRepository(BaseRepository[SyncRun]):
    """Database operations for integration synchronization runs."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SyncRun)

    def list_by_integration(
        self,
        integration: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SyncRun]:
        """Return synchronization runs for an integration."""
        statement = (
            select(SyncRun)
            .where(SyncRun.integration == integration)
            .order_by(SyncRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def list_by_status(
        self,
        status: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SyncRun]:
        """Return synchronization runs matching a status."""
        statement = (
            select(SyncRun)
            .where(SyncRun.status == status)
            .order_by(SyncRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class MockRequestLogRepository(BaseRepository[MockRequestLog]):
    """Database operations for simulator request logs."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, MockRequestLog)

    def list_by_integration(
        self,
        integration: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MockRequestLog]:
        """Return request logs for an integration."""
        statement = (
            select(MockRequestLog)
            .where(MockRequestLog.integration == integration)
            .order_by(MockRequestLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def list_by_status_code(
        self,
        status_code: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MockRequestLog]:
        """Return request logs matching an HTTP status code."""
        statement = (
            select(MockRequestLog)
            .where(MockRequestLog.status_code == status_code)
            .order_by(MockRequestLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())