"""Business logic for BRD-aligned Tenable vulnerability findings with idempotency and large-dataset support."""

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tenable import TenableFinding, TenableFindingCVE, TenableScan
from app.providers.tenable_normalizer import normalize_tenable_record
from app.repositories.tenable import TenableFindingRepository, TenableScanRepository
from app.schemas.tenable import TenableFindingCreate, TenableScanCreate


class TenableService:
    """Coordinate Tenable providers and PostgreSQL persistence with high-performance batching."""

    def __init__(self, db: Session, provider: Any) -> None:
        self.db = db
        self.repository = TenableFindingRepository(db)
        self.scan_repository = TenableScanRepository(db)
        self.provider = provider

    def list_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        severity: str | None = None,
        ip_address: str | None = None,
        include_informational: bool = False,
    ) -> dict[str, Any]:
        """List persisted findings supporting up to 50k records; hide informational records by default."""
        if limit < 1 or limit > 50000:
            raise ValueError("limit must be between 1 and 50000")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        provider_page_ids: list[str] | None = None
        provider_page_has_more = False
        if get_settings().provider_for("tenable") == "api":
            imported = self.import_provider_findings(
                limit=limit, offset=offset, include_source_ids=True
            )
            provider_page_ids = imported["source_finding_ids"]
            provider_page_has_more = imported["records_received"] == limit
        elif self.db.query(TenableFinding).count() == 0:
            self.import_provider_findings(limit=50000)

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

        if provider_page_ids is not None:
            query = query.filter(TenableFinding.source_finding_id.in_(provider_page_ids)) if provider_page_ids else query.filter(False)
            rows = query.all()
            by_source_id = {row.source_finding_id: row for row in rows}
            items = [by_source_id[key] for key in provider_page_ids if key in by_source_id]
            total = len(items)
            has_more = provider_page_has_more
        else:
            total = query.count()
            items = query.order_by(TenableFinding.id).offset(offset).limit(limit).all()
            has_more = offset + len(items) < total

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    def get_finding(self, finding_id: int) -> TenableFinding | None:
        """Retrieve a persisted finding by its database ID."""
        return self.repository.get_by_id(finding_id)

    def create_finding(
        self,
        payload: TenableFindingCreate,
    ) -> TenableFinding:
        """Idempotently create or update a finding and its CVEs in one transaction."""
        data = payload.model_dump(exclude={"cve_ids"})
        cve_ids = payload.cve_ids

        source_id = data.get("source_finding_id")

        try:
            # Check for existing record to enforce idempotency
            existing: TenableFinding | None = None
            if source_id:
                existing = self.repository.get_by_source_id(source_id)

            if existing is not None:
                for key, val in data.items():
                    setattr(existing, key, val)
                self._replace_cves(existing, cve_ids)
                self.db.commit()
                self.db.refresh(existing)
                return existing

            finding = self.repository.create(data)
            finding.cves = [
                TenableFindingCVE(cve=cve)
                for cve in sorted(set(cve_ids))
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
            and isinstance(payload.get("raw_record"), dict)
            and isinstance(payload.get("finding_source_fields"), dict)
            and isinstance(payload.get("normalization_metadata"), dict)
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
        limit: int = 50000,
        offset: int = 0,
        include_source_ids: bool = False,
    ) -> dict[str, Any]:
        """Normalize and idempotently upsert findings from the provider in optimized batches.

        Processes up to 50k records efficiently in chunks of 500 with batch commits,
        eliminating transaction bottlenecks and preventing duplicate key conflicts.
        """
        raw_records = self.provider.list_findings(
            limit=limit,
            offset=offset,
        )

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

        created = 0
        updated = 0
        skipped_without_identity = 0
        informational_retained = 0
        errors = 0

        # Deduplicate records by source_finding_id first
        clean_batch: list[tuple[str, dict[str, Any], list[str], bool]] = []
        seen_ids: set[str] = set()
        referenced_scan_ids = {
            str(record.get("scan_id")).strip()
            for record in raw_records
            if record.get("scan_id") not in (None, "")
        }
        scan_id_map = {
            source_id: database_id
            for source_id, database_id in self.db.query(
                TenableScan.source_scan_id, TenableScan.id
            ).filter(TenableScan.source_scan_id.in_(referenced_scan_ids)).all()
        } if referenced_scan_ids else {}

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
                metadata = source_payload.get("normalization_metadata") or {}
                is_info = (metadata.get("actionable") is False)

                if is_info:
                    informational_retained += 1

                cve_ids = normalized.get("cve_ids") or []
                data = {
                    key: value
                    for key, value in normalized.items()
                    if key in allowed_fields
                }
                source_scan_id = normalized.get("scan_id")
                data["scan_id"] = scan_id_map.get(str(source_scan_id).strip()) if source_scan_id not in (None, "") else None
                clean_batch.append((source_id, data, cve_ids, is_info))
            except Exception:
                errors += 1

        # Process clean records in chunks of 500
        chunk_size = 500
        for i in range(0, len(clean_batch), chunk_size):
            chunk = clean_batch[i : i + chunk_size]
            chunk_source_ids = [item[0] for item in chunk]
            created_before_chunk = created
            updated_before_chunk = updated

            try:
                existing_map = {
                    f.source_finding_id: f
                    for f in self.db.query(TenableFinding)
                    .filter(TenableFinding.source_finding_id.in_(chunk_source_ids))
                    .all()
                }

                for source_id, data, cve_ids, _ in chunk:
                    finding = existing_map.get(source_id)
                    if finding is None:
                        finding = TenableFinding(**data)
                        self.db.add(finding)
                        self._replace_cves(finding, cve_ids)
                        created += 1
                    else:
                        for k, v in data.items():
                            setattr(finding, k, v)
                        self._replace_cves(finding, cve_ids)
                        updated += 1

                self.db.commit()

            except Exception:
                self.db.rollback()
                created = created_before_chunk
                updated = updated_before_chunk
                # Process item by item in fallback to record partial successes
                for source_id, data, cve_ids, _ in chunk:
                    try:
                        finding = self.repository.get_by_source_id(source_id)
                        if finding is None:
                            finding = TenableFinding(**data)
                            self.db.add(finding)
                            self.db.flush()
                            self._replace_cves(finding, cve_ids)
                            created += 1
                        else:
                            for k, v in data.items():
                                setattr(finding, k, v)
                            self._replace_cves(finding, cve_ids)
                            updated += 1
                        self.db.commit()
                    except Exception:
                        self.db.rollback()
                        errors += 1

        scans_batch: list[dict[str, Any]] = []
        scan_ids: list[str] = []
        # Also import provider scans if available
        if hasattr(self.provider, "list_scans"):
            try:
                scans_batch = self.provider.list_scans(limit=limit, offset=offset)
                scan_ids = [
                    str(s.get("id") or s.get("source_scan_id") or "").strip()
                    for s in scans_batch
                    if str(s.get("id") or s.get("source_scan_id") or "").strip()
                ]
                existing_scan_ids = {
                    s[0]
                    for s in self.db.query(TenableScan.source_scan_id)
                    .filter(TenableScan.source_scan_id.in_(scan_ids))
                    .all()
                }
                for s in scans_batch:
                    scan_id = str(s.get("id") or s.get("source_scan_id") or "").strip()
                    if scan_id and scan_id not in existing_scan_ids:
                        self.db.add(TenableScan(
                            source_scan_id=scan_id,
                            name=s.get("name", f"Scan {scan_id}"),
                            status=s.get("status", "completed"),
                            source_payload=s,
                        ))
                        existing_scan_ids.add(scan_id)
                self.db.commit()
            except Exception:
                self.db.rollback()

        result = {
            "records_received": len(raw_records),
            "created": created,
            "updated": updated,
            "skipped_without_source_identity": skipped_without_identity,
            "informational_records_retained": informational_retained,
            "errors": errors,
            "source_offset": offset,
            "source_limit": limit,
        }
        if include_source_ids:
            result["source_finding_ids"] = [item[0] for item in clean_batch]
            result["source_scan_ids"] = scan_ids
            result["scan_records_received"] = len(scans_batch)
        return result

    def list_scans(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List persisted Tenable scans in PostgreSQL supporting up to 50k."""
        if limit < 1 or limit > 50000:
            raise ValueError("limit must be between 1 and 50000")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        provider_page_ids: list[str] | None = None
        provider_page_has_more = False
        if get_settings().provider_for("tenable") == "api":
            imported = self.import_provider_findings(
                limit=limit, offset=offset, include_source_ids=True
            )
            provider_page_ids = imported["source_scan_ids"]
            provider_page_has_more = imported["scan_records_received"] == limit
        elif self.db.query(TenableScan).count() == 0:
            self.import_provider_findings(limit=50000)

        query = self.db.query(TenableScan)
        if provider_page_ids is not None:
            query = query.filter(TenableScan.source_scan_id.in_(provider_page_ids)) if provider_page_ids else query.filter(False)
            rows = query.all()
            by_source_id = {row.source_scan_id: row for row in rows}
            items = [by_source_id[key] for key in provider_page_ids if key in by_source_id]
            total = len(items)
            has_more = provider_page_has_more
        else:
            total = query.count()
            items = query.order_by(TenableScan.id).offset(offset).limit(limit).all()
            has_more = offset + len(items) < total

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    def get_scan(self, scan_id: int) -> TenableScan | None:
        """Retrieve a scan by its database ID."""
        return self.scan_repository.get_by_id(scan_id)

    def create_scan(self, payload: TenableScanCreate) -> TenableScan:
        """Idempotently create or update a scan record in PostgreSQL."""
        data = payload.model_dump()
        source_id = data.get("source_scan_id")
        try:
            if source_id:
                existing = self.scan_repository.get_by_source_id(source_id)
                if existing:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    self.db.commit()
                    self.db.refresh(existing)
                    return existing

            scan = self.scan_repository.create(data)
            self.db.commit()
            self.db.refresh(scan)
            return scan
        except Exception:
            self.db.rollback()
            raise

    def list_provider_scans(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List scans from the active Tenable provider (JSON or API)."""
        if hasattr(self.provider, "list_scans"):
            return self.provider.list_scans(limit=limit, offset=offset)
        return []

    def create_provider_finding(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Idempotently create or update a finding in the active provider."""
        if hasattr(self.provider, "create_finding"):
            return self.provider.create_finding(payload)
        raise ValueError("Active provider does not support creating findings")
