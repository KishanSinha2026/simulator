
from typing import Any

from app.providers.json_provider import JsonProvider


class TenableJsonProvider(JsonProvider):
    """Tenable findings provider backed by local JSON fixtures."""

    def __init__(
        self,
        fixture_name: str = "tenable/findings.json",
    ) -> None:
        super().__init__(fixture_name)

    def get_finding(
        self,
        finding_id: str,
    ) -> dict[str, Any] | None:
        return self.get_by_id(finding_id)

    def list_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def create_finding(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        required_fields = ("plugin_id", "ip_address", "severity")
        missing_fields = [
            field
            for field in required_fields
            if payload.get(field) is None
        ]

        if missing_fields:
            raise ValueError(
                "Missing required Tenable finding fields: "
                + ", ".join(missing_fields)
            )

        return self.create_record(payload)
