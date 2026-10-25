"""Business logic for BMC Helix ITSM change requests."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories.itsm import ITSMChangeRepository
from app.schemas.itsm import ITSMChangeCreate, ITSMChangeUpdate


class ITSMService:
    """Coordinate ITSM change operations and database persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ITSMChangeRepository(db)

    def list_changes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List persisted changes with optional status filtering."""
        query = self.db.query(self.repository.model)

        if status:
            query = query.filter(
                self.repository.model.status == status
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

    def get_change(self, change_id: int) -> Any:
        """Retrieve a change by its database ID."""
        return self.repository.get_by_id(change_id)

    def create_change(self, payload: ITSMChangeCreate) -> Any:
        """Create a simulated ITSM change in PostgreSQL."""
        data = payload.model_dump()

        if (
            data.get("scheduled_start")
            and data.get("scheduled_end")
            and data["scheduled_end"] <= data["scheduled_start"]
        ):
            raise ValueError(
                "scheduled_end must be later than scheduled_start"
            )

        try:
            record = self.repository.create(data)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    def update_change(
        self,
        change_id: int,
        payload: ITSMChangeUpdate,
    ) -> Any | None:
        """Update selected fields of a persisted change."""
        record = self.repository.get_by_id(change_id)
        if record is None:
            return None

        changes = payload.model_dump(exclude_unset=True)
        start = changes.get("scheduled_start", record.scheduled_start)
        end = changes.get("scheduled_end", record.scheduled_end)

        if start and end and end <= start:
            raise ValueError(
                "scheduled_end must be later than scheduled_start"
            )

        try:
            record = self.repository.update(record, changes)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise