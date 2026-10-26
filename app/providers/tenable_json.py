"""JSON fixture provider for Tenable vulnerability findings."""

from typing import Any
from uuid import uuid4

from app.providers.json_provider import JsonProvider
from app.providers.tenable_normalizer import normalize_tenable_record


class TenableJsonProvider(JsonProvider):
    """Read and create simulated Tenable findings using JSON fixtures."""

    def __init__(
        self,
        fixture_name: str = "tenable/findings.json",
    ) -> None:
        super().__init__(fixture_name)
        self.scans = JsonProvider("tenable/scans.json")

    @staticmethod
    def _normalize(record: dict[str, Any]) -> dict[str, Any]:
        """Normalize a fixture record while retaining its original data."""
        return normalize_tenable_record(record)

    def list_scans(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List simulated scans from the JSON fixture."""
        return self.scans.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def get_scan(
        self,
        scan_id: str,
    ) -> dict[str, Any] | None:
        """Find a scan by simulator ID or external source ID."""
        record = self.scans.get_by_id(scan_id)
        if record is not None:
            return record

        matches = self.scans.list_records(
            limit=1000,
            filters={"source_scan_id": scan_id},
        )
        return matches[0] if matches else None

    def create_scan(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a simulated scan in the JSON fixture."""
        if not payload:
            raise ValueError("Scan payload cannot be empty")

        record = dict(payload)
        source_scan_id = record.get("source_scan_id")
        if not source_scan_id or not str(source_scan_id).strip():
            record["source_scan_id"] = f"scan-{uuid4().hex[:8]}"
        else:
            record["source_scan_id"] = str(source_scan_id).strip()

        record.setdefault("id", record["source_scan_id"])
        record.setdefault("status", "completed")
        return self.scans.create_record(record)

    def get_finding(
        self,
        finding_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a finding by simulator ID or external finding ID."""
        record = self.get_by_id(finding_id)

        if record is not None:
            return self._normalize(record)

        matches = self.list_records(
            limit=10000,
            filters={"source_finding_id": finding_id},
        )

        return self._normalize(matches[0]) if matches else None

    def list_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List normalized fixture findings with optional filters."""
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        records = self.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

        return [
            self._normalize(record)
            for record in records
        ]

    def create_finding(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a simulated finding in the JSON fixture."""
        if not payload:
            raise ValueError("Finding payload cannot be empty")

        record = dict(payload)

        plugin_id = record.get("plugin_id")
        if (
            not isinstance(plugin_id, int)
            or isinstance(plugin_id, bool)
            or plugin_id <= 0
        ):
            raise ValueError("plugin_id must be a positive integer")

        plugin_name = record.get("plugin_name")
        if not isinstance(plugin_name, str) or not plugin_name.strip():
            raise ValueError("plugin_name is required and cannot be blank")

        record["plugin_name"] = plugin_name.strip()

        source_finding_id = record.get("source_finding_id")

        if source_finding_id is not None:
            source_finding_id = str(source_finding_id).strip()

            if not source_finding_id:
                raise ValueError("source_finding_id cannot be blank")

            existing = self.list_records(
                limit=10000,
                filters={"source_finding_id": source_finding_id},
            )

            if existing:
                raise ValueError(
                    "A finding with this source_finding_id already exists"
                )

            record["source_finding_id"] = source_finding_id
        else:
            record["source_finding_id"] = f"tnb-{uuid4().hex}"

        record.setdefault("id", record["source_finding_id"])

        if self.get_by_id(str(record["id"])) is not None:
            raise ValueError(
                f"A finding with ID {record['id']!r} already exists"
            )

        return self.create_record(record)