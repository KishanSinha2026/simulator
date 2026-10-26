"""Business logic for Tenable vulnerability findings and source ingestion.

The import method is deliberately idempotent on a stable source_finding_id.
It does not fabricate identifiers from plugin IDs because a plugin can affect
multiple hosts. Records without a reliable source identity are skipped and
reported, until the configured source API supplies an approved finding key.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.tenable import TenableFindingCVE
from app.providers.factory import get_provider
from app.providers.tenable_normalizer import normalize_tenable_record
from app.repositories.tenable import TenableFindingRepository
from app.schemas.tenable import TenableFindingCreate


# The DB model currently contains only this normalized subset. All other BRD
# fields are retained in source_payload["_brd_54_fields"] by the normalizer.
_DB_FINDING_FIELDS = (
    "source_finding_id",
    "scan_id",
    "plugin_id",
    "plugin_name",
    "ip_address",
    "dns_name",
    "host_id",
    "severity",
    "synopsis",
    "description",
    "plugin_output",
    "steps_to_remediate",
    "cvss_v3_base_score",
    "cvss_v4_base_score",
    "first_discovered",
    "last_observed",
    "repository",
    "protocol",
    "port",
    "source_payload",
)


class TenableService:
    """Coordinate Tenable providers and PostgreSQL persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TenableFindingRepository(db)
        self.provider = get_provider("tenable")

    def list_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        severity: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """List persisted findings with optional filters."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        query = self.db.query(self.repository.model)

        if severity:
            normalized_severity = severity.strip().lower()
            if normalized_severity in {"info", "informational"}:
                query = query.filter(
                    self.repository.model.severity.in_(
                        ["info", "informational"]
                    )
                )
            else:
                query = query.filter(
                    self.repository.model.severity == normalized_severity
                )

        if ip_address:
            query = query.filter(
                self.repository.model.ip_address == ip_address.strip()
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

    def get_finding(self, finding_id: int) -> Any | None:
        """Retrieve a persisted finding by its database ID."""
        return self.repository.get_by_id(finding_id)

    def create_finding(self, payload: TenableFindingCreate) -> Any:
        """Create a finding and its CVE associations atomically."""
        data = payload.model_dump(exclude={"cve_ids"})
        cve_ids = payload.cve_ids

        try:
            finding = self.repository.create(data)
            finding.cves = [TenableFindingCVE(cve=cve) for cve in cve_ids]
            self.db.flush()
            self.db.commit()
            self.db.refresh(finding)
            return finding
        except Exception:
            self.db.rollback()
            raise

    def list_provider_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch source findings without persisting them."""
        return self.provider.list_findings(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    @staticmethod
    def _normalize_provider_record(
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize a provider record once, preserving existing BRD mapping."""
        existing_payload = record.get("source_payload")
        if (
            isinstance(existing_payload, dict)
            and isinstance(existing_payload.get("_brd_54_fields"), dict)
        ):
            return dict(record)

        return normalize_tenable_record(record)

    @staticmethod
    def _extract_cves(record: dict[str, Any]) -> list[str]:
        """Return unique, non-empty CVE identifiers in normalized form."""
        values = record.get("cve_ids") or []
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, (list, tuple, set)):
            return []

        result: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip().upper()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def import_provider_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Import source findings idempotently into PostgreSQL.

        Informational findings are retained for traceability but counted
        separately. Actionable workflows must exclude rows whose normalized
        severity is informational. Records without a stable source identifier
        are not persisted to avoid duplicates; this is important for the
        current plugin-level Workbench endpoint.
        """
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        source_records = self.provider.list_findings(
            limit=limit,
            offset=offset,
            filters=filters,
        )
        if not isinstance(source_records, list):
            raise RuntimeError("Tenable provider did not return a list")

        counts: dict[str, int] = {
            "received": len(source_records),
            "created": 0,
            "updated": 0,
            "skipped_missing_source_identity": 0,
            "skipped_invalid_record": 0,
            "informational_retained": 0,
        }
        skipped: list[dict[str, str]] = []

        try:
            for index, raw_record in enumerate(source_records):
                if not isinstance(raw_record, dict):
                    counts["skipped_invalid_record"] += 1
                    skipped.append({
                        "index": str(index),
                        "reason": "record is not a JSON object",
                    })
                    continue

                record = self._normalize_provider_record(raw_record)
                source_id = record.get("source_finding_id")
                if source_id is not None:
                    source_id = str(source_id).strip()

                if not source_id:
                    counts["skipped_missing_source_identity"] += 1
                    skipped.append({
                        "index": str(index),
                        "reason": (
                            "stable source_finding_id is absent; refusing to "
                            "invent an ID from plugin_id"
                        ),
                    })
                    continue

                payload = {
                    field: record.get(field)
                    for field in _DB_FINDING_FIELDS
                    if field in record
                }
                payload["source_finding_id"] = source_id
                payload["source_payload"] = record.get("source_payload") or {}

                # Do not erase a stored value with null merely because the
                # selected API does not return that field in this response.
                existing = self.repository.get_by_source_id(source_id)
                cve_ids = self._extract_cves(record)

                severity = str(record.get("severity") or "").strip().lower()
                if severity in {"info", "informational"}:
                    payload["severity"] = "informational"
                    counts["informational_retained"] += 1

                if existing is None:
                    # Keep only model fields; no provider-only extras such as
                    # normalized_cvss_base_score are sent to SQLAlchemy.
                    create_payload = {
                        key: value for key, value in payload.items()
                        if key in _DB_FINDING_FIELDS
                    }
                    finding = self.repository.create(create_payload)
                    finding.cves = [
                        TenableFindingCVE(cve=cve) for cve in cve_ids
                    ]
                    counts["created"] += 1
                else:
                    update_payload = {
                        key: value for key, value in payload.items()
                        if key in _DB_FINDING_FIELDS
                        and (value is not None or key == "source_payload")
                    }
                    self.repository.update(existing, update_payload)
                    if cve_ids:
                        existing.cves = [
                            TenableFindingCVE(cve=cve) for cve in cve_ids
                        ]
                    counts["updated"] += 1

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            **counts,
            "skipped": skipped,
            "actionable_records_created_or_updated": (
                counts["created"] + counts["updated"]
                - counts["informational_retained"]
            ),
            "message": (
                "Import finished. Informational records are retained for "
                "traceability; downstream actionable workflows must exclude "
                "them. Records without stable source identity were skipped."
            ),
        }
