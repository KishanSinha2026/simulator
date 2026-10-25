
from typing import Any

from app.providers.json_provider import JsonProvider


class ITSMJsonProvider:
    """BMC Helix ITSM adapter backed by local JSON fixtures."""

    def __init__(self) -> None:
        self.changes = JsonProvider("itsm/changes.json")
        self.worklogs = JsonProvider("itsm/worklogs.json")

    def get_change(self, change_id: str) -> dict[str, Any] | None:
        return self.changes.get_by_id(change_id)

    def list_changes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.changes.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def create_change(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        required_fields = (
            "summary",
            "impact",
            "urgency",
            "description",
        )
        missing_fields = [
            field for field in required_fields
            if payload.get(field) is None or payload.get(field) == ""
        ]

        if missing_fields:
            raise ValueError(
                "Missing required ITSM change fields: "
                + ", ".join(missing_fields)
            )

        return self.changes.create_record(payload)

    def list_worklogs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.worklogs.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )
