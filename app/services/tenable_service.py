"""Business logic for BRD-aligned Tenable vulnerability findings."""

from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tenable import TenableFinding, TenableFindingCVE
from app.providers.factory import get_provider
from app.providers.tenable_normalizer import normalize_tenable_record
from app.repositories.tenable import TenableFindingRepository
from app.schemas.tenable import TenableFindingCreate


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
        include_informational: bool = False,
    ) -> dict[str, Any]:
        """List persisted findings; hide informational records by default."""
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        query = self.db.query(TenableFinding)

        if severity:
            query = query.filter(
                func.lower(TenableFinding.severity)
                == severity.strip().lower()
            )

        if ip_address:
            query = query.filter(
                TenableFinding.ip_address == ip_address.strip()
            )

        if not include_informational:
            query = query.filter(
                func.lower(func.coalesce(TenableFinding.severity, ""))
                .notin_(("info", "informational"))
            )

        total = query.count()

        items = (
            query.order_by(TenableFinding.id)
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

    def get_finding(self, finding_id: int) -> TenableFinding | None:
        """Retrieve a persisted finding by its database ID."""
        return self.repository.get_by_id(finding_id)

    def create_finding(
        self,
        payload: TenableFindingCreate,
    ) -> TenableFinding:
        """Create a simulated finding and its CVEs in one transaction."""
        data = payload.model_dump(exclude={"cve_ids"})
        cve_ids = payload.cve_ids

        try:
            finding = self.repository.create(data)
            finding.cves = [
                TenableFindingCVE(cve=cve)
                for cve in cve_ids
            ]

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
        """Read source findings without persisting them."""
        return self.provider.list_findings(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    @staticmethod
    def _prepare_provider_record(
        raw_record: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize fixture records; avoid normalizing API output twice."""
        payload = raw_record.get("source_payload")

        if (
            isinstance(payload, dict)
            and isinstance(payload.get("_brd_54_fields"), dict)
            and isinstance(payload.get("_brd_normalization"), dict)
        ):
            return raw_record

        return normalize_tenable_record(raw_record)

    @staticmethod
    def _replace_cves(
        finding: TenableFinding,
        cve_ids: list[str],
    ) -> None:
        """Replace CVE associations with the complete source list."""
        existing = {association.cve for association in finding.cves}
        incoming = set(cve_ids)

        if existing == incoming:
            return

        finding.cves = [
            TenableFindingCVE(cve=cve)
            for cve in sorted(incoming)
        ]

    def import_provider_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Normalize and idempotently upsert findings from the provider.

        Existing normalized columns are populated where applicable.
        The original 54-field snapshot is retained in source_payload.
        Informational records remain stored but are not actionable.
        """
        raw_records = self.provider.list_findings(
            limit=limit,
            offset=offset,
        )

        created = 0
        updated = 0
        skipped_without_identity = 0
        informational_retained = 0
        errors = 0
        seen_ids: set[str] = set()

        try:
            for raw_record in raw_records:
                try:
                    normalized = self._prepare_provider_record(raw_record)

                    source_id = normalized.get("source_finding_id")
                    if source_id is None or not str(source_id).strip():
                        skipped_without_identity += 1
                        continue

                    source_id = str(source_id).strip()

                    if source_id in seen_ids:
                        continue
                    seen_ids.add(source_id)

                    source_payload = normalized.get("source_payload") or {}
                    metadata = source_payload.get("_brd_normalization") or {}

                    if metadata.get("actionable") is False:
                        informational_retained += 1

                    cve_ids = normalized.get("cve_ids") or []

                    # Only columns defined on the existing model may be sent
                    # to SQLAlchemy. Extra BRD fields remain in JSONB.
                    allowed_fields = {
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
                    }

                    data = {
                        key: value
                        for key, value in normalized.items()
                        if key in allowed_fields
                    }

                    # Isolate each record so one bad row does not silently
                    # roll back all earlier source records in the batch.
                    with self.db.begin_nested():
                        finding = self.repository.get_by_source_id(source_id)

                        if finding is None:
                            finding = TenableFinding(**data)
                            self.db.add(finding)
                            self.db.flush()
                            created += 1
                        else:
                            for key, value in data.items():
                                setattr(finding, key, value)
                            self.db.flush()
                            updated += 1

                        self._replace_cves(finding, cve_ids)
                        self.db.flush()

                except IntegrityError:
                    errors += 1
                except (TypeError, ValueError):
                    errors += 1

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        return {
            "records_received": len(raw_records),
            "created": created,
            "updated": updated,
            "skipped_without_source_identity": skipped_without_identity,
            "informational_records_retained": informational_retained,
            "errors": errors,
            "source_offset": offset,
            "source_limit": limit,
        }