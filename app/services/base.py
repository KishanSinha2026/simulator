"""Base classes and shared helpers for integration services."""

from abc import ABC
from typing import Any

from sqlalchemy.orm import Session


class BaseService(ABC):
    """Base service providing database transaction helpers.

    Services coordinate repositories and providers. They should not
    commit independently during a multi-step business operation unless
    the transaction boundary explicitly requires it.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        """Commit the current database transaction."""
        self.db.commit()

    def rollback(self) -> None:
        """Roll back the current database transaction."""
        self.db.rollback()

    def flush(self) -> None:
        """Flush pending changes without committing."""
        self.db.flush()

    @staticmethod
    def normalize_record(
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a shallow copy of a provider record."""
        return dict(record)
    