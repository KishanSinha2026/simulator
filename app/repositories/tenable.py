"""Database repository for Tenable vulnerability findings."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenable import TenableFinding
from app.repositories.base import BaseRepository


class TenableFindingRepository(BaseRepository[TenableFinding]):
    """Database operations specific to Tenable findings."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, TenableFinding)

    def get_by_source_id(self, source_id: str) -> TenableFinding | None:
        """Find a finding by its external source identifier."""
        statement = select(TenableFinding).where(
            TenableFinding.source_id == source_id
        )
        return self.db.scalars(statement).first()

    def list_by_severity(
        self,
        severity: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TenableFinding]:
        """Return findings matching a severity value."""
        statement = (
            select(TenableFinding)
            .where(TenableFinding.severity == severity)
            .order_by(TenableFinding.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def list_by_ip(
        self,
        ip_address: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TenableFinding]:
        """Return findings associated with an IP address."""
        statement = (
            select(TenableFinding)
            .where(TenableFinding.ip_address == ip_address)
            .order_by(TenableFinding.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())