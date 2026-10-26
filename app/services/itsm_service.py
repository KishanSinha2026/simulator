"""Business logic for BMC Helix ITSM change requests."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories.itsm import ITSMChangeRepository
from app.schemas.itsm import ITSMChangeCreate, ITSMChangeUpdate


class ITSMService:
    """Coordinate ITSM change operations and PostgreSQL persistence."""

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
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        query = self.db.query(self.repository.model)

        if status:
            query = query.filter(
                self.repository.model.status == status
            )

        total = query.count()

        items = (
            query
            .order_by(self.repository.model.id)
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

    def get_change(self, change_id: int) -> Any | None:
        """Retrieve a change request by its database ID."""
        return self.repository.get_by_id(change_id)

    @staticmethod
    def _validate_schedule(
        scheduled_start_at: Any | None,
        scheduled_end_at: Any | None,
    ) -> None:
        """Validate the scheduled window of a change request."""
        if (
            scheduled_start_at is not None
            and scheduled_end_at is not None
            and scheduled_end_at <= scheduled_start_at
        ):
            raise ValueError(
                "scheduled_end_at must be later than scheduled_start_at"
            )

    def create_change(self, payload: ITSMChangeCreate) -> Any:
        """Create a simulated change request in PostgreSQL."""
        data = payload.model_dump()

        self._validate_schedule(
            data.get("scheduled_start_at"),
            data.get("scheduled_end_at"),
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
        """Update selected fields of a persisted change request."""
        record = self.repository.get_by_id(change_id)

        if record is None:
            return None

        changes = payload.model_dump(exclude_unset=True)

        scheduled_start_at = changes.get(
            "scheduled_start_at",
            record.scheduled_start_at,
        )
        scheduled_end_at = changes.get(
            "scheduled_end_at",
            record.scheduled_end_at,
        )

        self._validate_schedule(
            scheduled_start_at,
            scheduled_end_at,
        )

        try:
            record = self.repository.update(record, changes)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise