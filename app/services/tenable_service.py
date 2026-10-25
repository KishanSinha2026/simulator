"""Business logic for Tenable vulnerability findings."""

from typing import Any

from sqlalchemy.orm import Session

from app.providers.factory import get_provider
from app.repositories.tenable import TenableFindingRepository
from app.schemas.tenable import TenableFindingCreate


class TenableService:
    """Coordinate Tenable providers and PostgreSQL persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TenableFindingRepository(db)
        self.provider = get_provider("tenable")

    def list_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        severity: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """List persisted findings with optional filters."""
        query = self.db.query(self.repository.model)

        if severity:
            query = query.filter(
                self.repository.model.severity == severity
            )

        if ip_address:
            query = query.filter(
                self.repository.model.ip_address == ip_address
            )

        total = query.count()
        items = (
            query.order_by(self.repository.model.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    def get_finding(self, finding_id: int) -> Any:
        """Retrieve a persisted finding by database ID."""
        return self.repository.get_by_id(finding_id)

    def create_finding(
        self,
        payload: TenableFindingCreate,
    ) -> Any:
        """Create a simulator finding and persist it."""
        data = payload.model_dump()

        try:
            record = self.repository.create(data)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    def list_provider_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Retrieve findings from the configured provider.

        This does not automatically persist provider records.
        """
        return self.provider.list_findings(
            limit=limit,
            offset=offset,
        )