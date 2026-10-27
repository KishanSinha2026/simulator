"""JSON fixture provider for Squad1 vulnerability lifecycle simulation."""

from typing import Any
from uuid import uuid4

from app.providers.json_provider import JsonProvider


class Squad1JsonProvider:
    """Read and manage simulated Squad1 records in JSON files."""

    def __init__(self) -> None:
        self.vulnerabilities = JsonProvider("squad1/vulnerabilities.json")

    def list_vulnerabilities(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List Squad1 vulnerabilities with optional filters and pagination."""
        if not 1 <= limit <= 50000:
            raise ValueError("limit must be between 1 and 50000")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        return self.vulnerabilities.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def get_vulnerability(self, vulnerability_id: str) -> dict[str, Any] | None:
        """Retrieve a vulnerability by its internal fixture ID."""
        return self.vulnerabilities.get_by_id(vulnerability_id)

    def get_by_vulnerability_no(self, vulnerability_no: str) -> dict[str, Any] | None:
        """Find record by external VulnerabilityNo."""
        norm_no = vulnerability_no.strip()
        records = self.vulnerabilities.list_records(limit=50000)
        for record in records:
            if record.get("vulnerability_no", "").strip() == norm_no:
                return record
        return None

    def list_exceptions(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List active exception records per BRD Section 4.2."""
        records = self.vulnerabilities.list_records(limit=50000)
        exceptions = [
            r for r in records
            if r.get("exception_id") is not None and str(r.get("exception_id")).strip()
        ]
        return exceptions[offset : offset + limit]

    def create_vulnerability(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create or idempotently update a vulnerability record."""
        data = dict(payload)
        vuln_no = str(data.get("vulnerability_no", "")).strip()
        if not vuln_no:
            raise ValueError("vulnerability_no is required")

        existing = self.get_by_vulnerability_no(vuln_no)
        if existing is not None:
            data["id"] = existing["id"]
            return self.vulnerabilities.update_record(existing["id"], data)

        if not data.get("id"):
            data["id"] = f"sq1-{uuid4().hex[:8]}"

        return self.vulnerabilities.create_record(data)
