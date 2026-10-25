
from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """Common interface for simulator data providers."""

    @abstractmethod
    def get_by_id(self, record_id: str) -> dict[str, Any] | None:
        """Return one record by its source identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_records(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return records with optional filters and pagination."""
        raise NotImplementedError

    @abstractmethod
    def create_record(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a record or simulate the corresponding operation."""
        raise NotImplementedError
