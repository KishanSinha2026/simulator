"""JSON fixture provider for BMC Helix ITSM simulation."""

from typing import Any
from uuid import uuid4

from app.providers.json_provider import JsonProvider


class ITSMJsonProvider:
    """Read and create simulated ITSM changes using JSON fixtures."""

    def __init__(self) -> None:
        self.changes = JsonProvider("itsm/changes.json")
        self.worklogs = JsonProvider("itsm/worklogs.json")

    def get_change(
        self,
        change_id: str,
    ) -> dict[str, Any] | None:
        """Find a change by simulator ID or external change ID."""
        record = self.changes.get_by_id(change_id)

        if record is not None:
            return record

        matches = self.changes.list_records(
            limit=10000,
            filters={"source_change_id": change_id},
        )

        return matches[0] if matches else None

    def list_changes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List simulated changes with optional filters."""
        return self.changes.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def create_change(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a simulated change in the JSON fixture."""
        if not payload:
            raise ValueError("Change payload cannot be empty")

        record = dict(payload)

        source_change_id = record.get("source_change_id")
        if not isinstance(source_change_id, str) or not source_change_id.strip():
            raise ValueError(
                "source_change_id is required and cannot be blank"
            )

        record["source_change_id"] = source_change_id.strip()

        existing = self.changes.list_records(
            limit=10000,
            filters={
                "source_change_id": record["source_change_id"],
            },
        )

        if existing:
            raise ValueError(
                "A change with this source_change_id already exists"
            )

        start = record.get("scheduled_start_at")
        end = record.get("scheduled_end_at")

        if start and end and end <= start:
            raise ValueError(
                "scheduled_end_at must be later than scheduled_start_at"
            )

        record.setdefault(
            "id",
            f"sim-change-{uuid4().hex}",
        )

        record.setdefault(
            "source_payload",
            {"is_simulated": True},
        )

        return self.changes.create_record(record)

    def list_worklogs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List simulated worklogs with optional filters."""
        return self.worklogs.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def create_worklog(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a simulated worklog in the JSON fixture."""
        if not payload:
            raise ValueError("Worklog payload cannot be empty")
        record = dict(payload)
        record.setdefault("id", f"worklog-{uuid4().hex[:8]}")
        record.setdefault("source_worklog_id", record["id"])
        record.setdefault("source_payload", {"is_simulated": True})
        return self.worklogs.create_record(record)