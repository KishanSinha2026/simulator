"""Base repository with common database operations."""

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Reusable CRUD operations for SQLAlchemy models."""

    def __init__(self, db: Session, model: type[ModelType]) -> None:
        self.db = db
        self.model = model

    def get_by_id(self, record_id: int) -> ModelType | None:
        """Return a record by its primary key."""
        return self.db.get(self.model, record_id)

    def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelType]:
        """Return records ordered by primary key."""
        statement = (
            select(self.model)
            .order_by(self.model.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def count(self) -> int:
        """Return the total number of records."""
        statement = select(func.count()).select_from(self.model)
        return int(self.db.scalar(statement) or 0)

    def create(self, payload: dict[str, Any]) -> ModelType:
        """Create and persist a record."""
        record = self.model(**payload)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def update(
        self,
        record: ModelType,
        payload: dict[str, Any],
    ) -> ModelType:
        """Update only the fields supplied by the caller."""
        for field, value in payload.items():
            if not hasattr(record, field):
                raise ValueError(
                    f"Unknown field {field!r} for {self.model.__name__}"
                )
            setattr(record, field, value)

        self.db.flush()
        self.db.refresh(record)
        return record

    def delete(self, record: ModelType) -> None:
        """Delete a record from the current transaction."""
        self.db.delete(record)
        self.db.flush()