"""Business logic for Squad1 vulnerability lifecycle management."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.squad1 import Squad1Vulnerability
from app.repositories.squad1 import Squad1Repository
from app.schemas.squad1 import Squad1VulnerabilityCreate


class Squad1Service:
    """Coordinate Squad1 vulnerability imports, exceptions, and updates."""

    def __init__(self, db: Session, provider: Any) -> None:
        self.db = db
        self.repository = Squad1Repository(db)
        self.provider = provider

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        """Validate pagination parameters."""
        if not 1 <= limit <= 50000:
            raise ValueError("limit must be between 1 and 50000")
        if offset < 0:
            raise ValueError("offset cannot be negative")

    @staticmethod
    def _source_value(record: dict[str, Any], *keys: str) -> Any:
        """Read the first populated normalized or exact BRD key."""
        for key in keys:
            value = record.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _source_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @staticmethod
    def _source_number(value: Any) -> float | None:
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def list_vulnerabilities(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        target: str | None = None,
        risk_rating: str | None = None,
    ) -> dict[str, Any]:
        """List Squad1 vulnerabilities with optional filters."""
        self._validate_pagination(limit, offset)

        # Auto-import from active provider if database is empty
        if self.db.query(Squad1Vulnerability).count() == 0:
            self.import_provider_data()

        query = self.db.query(Squad1Vulnerability)

        if status:
            query = query.filter(Squad1Vulnerability.status == status.strip())
        if target:
            query = query.filter(Squad1Vulnerability.target == target.strip())
        if risk_rating:
            query = query.filter(Squad1Vulnerability.risk_rating == risk_rating.strip())

        total = query.count()
        items = (
            query.order_by(Squad1Vulnerability.id)
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

    def get_vulnerability(self, vulnerability_id: int) -> Squad1Vulnerability | None:
        """Retrieve a vulnerability by its database ID."""
        if vulnerability_id < 1:
            raise ValueError("vulnerability_id must be greater than zero")
        return self.repository.get_by_id(vulnerability_id)

    def list_exceptions(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Retrieve active exceptions per BRD Section 4.2."""
        self._validate_pagination(limit, offset)

        if self.db.query(Squad1Vulnerability).count() == 0:
            self.import_provider_data()

        query = self.db.query(Squad1Vulnerability).filter(
            Squad1Vulnerability.exception_id.isnot(None),
            Squad1Vulnerability.exception_id != "",
            or_(
                Squad1Vulnerability.exception_end_date.is_(None),
                Squad1Vulnerability.exception_end_date >= datetime.now(timezone.utc),
            ),
        )
        total = query.count()
        items = (
            query.order_by(Squad1Vulnerability.id)
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

    def create_vulnerability(
        self,
        payload: Squad1VulnerabilityCreate,
    ) -> Squad1Vulnerability:
        """Idempotently create or update a Squad1 vulnerability."""
        dumped = payload.model_dump()
        column_names = set(Squad1Vulnerability.__table__.columns.keys())
        data = {key: value for key, value in dumped.items() if key in column_names}
        raw_payload = payload.model_dump(mode="json", exclude={"source_payload"})
        data["source_payload"] = {
            **raw_payload,
            **(payload.source_payload or {}),
        }
        vuln_no = data.get("vulnerability_no")

        if not vuln_no or not vuln_no.strip():
            raise ValueError("vulnerability_no is required and cannot be blank")

        vuln_no = vuln_no.strip()
        data["vulnerability_no"] = vuln_no

        try:
            existing = self.repository.get_by_vulnerability_no(vuln_no)
            if existing is not None:
                for k, v in data.items():
                    setattr(existing, k, v)
                self.db.commit()
                self.db.refresh(existing)
                return existing

            record = self.repository.create(data)
            self.db.commit()
            self.db.refresh(record)
            return record

        except Exception:
            self.db.rollback()
            raise

    def import_provider_data(
        self,
        *,
        limit: int = 50000,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Import Squad1 vulnerabilities from active provider into PostgreSQL."""
        raw_records = []
        if hasattr(self.provider, "list_vulnerabilities"):
            raw_records = self.provider.list_vulnerabilities(limit=limit, offset=offset)

        created = 0
        updated = 0
        errors = 0
        exceptions_count = 0

        clean_batch: list[tuple[str, dict[str, Any]]] = []
        seen_nos: set[str] = set()

        for raw in raw_records:
            try:
                vuln_no = str(
                    self._source_value(raw, "vulnerability_no", "VulnerabilityNo", "id") or ""
                ).strip()
                if not vuln_no or vuln_no in seen_nos:
                    continue
                seen_nos.add(vuln_no)

                if self._source_value(raw, "exception_id", "Exception_ID"):
                    exceptions_count += 1

                allowed_fields = {
                    "vulnerability_no",
                    "plugin_id",
                    "target",
                    "vulnerability_name",
                    "description",
                    "protocol",
                    "port",
                    "risk_rating",
                    "status",
                    "recommendation",
                    "solution_category",
                    "plugin_output",
                    "owasp_mapping",
                    "cve_id",
                    "cvss_score",
                    "risk_type",
                    "vulnerability_holder",
                    "vulnerability_holder_department",
                    "vulnerability_holder_location",
                    "bu_head",
                    "report_published_date",
                    "planned_remediation_date",
                    "ageing",
                    "risk_severity_change_date",
                    "exception_id",
                    "exception_end_date",
                    "exception_status",
                    "source_payload",
                }

                aliases = {
                    "plugin_id": ("plugin_id", "PluginID"),
                    "target": ("target", "Target"),
                    "vulnerability_name": ("vulnerability_name", "Vulnerability_Name"),
                    "description": ("description", "Description"),
                    "protocol": ("protocol", "Protocol"),
                    "port": ("port", "Port"),
                    "risk_rating": ("risk_rating", "Risk_Rating", "severity", "Severity"),
                    "status": ("status", "STATUS", "Status"),
                    "recommendation": ("recommendation", "Recommendation"),
                    "solution_category": ("solution_category", "Solution_Category"),
                    "plugin_output": ("plugin_output", "POC/Plugin Output"),
                    "owasp_mapping": ("owasp_mapping", "OWASP_mapping"),
                    "cve_id": ("cve_id", "CVE_ID"),
                    "cvss_score": ("cvss_score", "CVSS_Score"),
                    "risk_type": ("risk_type", "Risk_Type"),
                    "vulnerability_holder": ("vulnerability_holder", "Vulnerability_Holder"),
                    "vulnerability_holder_department": (
                        "vulnerability_holder_department", "Vulnerability_Holder_Department"
                    ),
                    "vulnerability_holder_location": (
                        "vulnerability_holder_location", "Vulnerability_Holder_Location"
                    ),
                    "bu_head": ("bu_head", "BU_Head"),
                    "report_published_date": ("report_published_date", "Report_Published_Date"),
                    "planned_remediation_date": ("planned_remediation_date", "PlannedRemediationDate"),
                    "ageing": ("ageing", "Ageing"),
                    "risk_severity_change_date": (
                        "risk_severity_change_date", "Risk_Severity_changeDate"
                    ),
                    "exception_id": ("exception_id", "Exception_ID"),
                    "exception_end_date": ("exception_end_date", "Exception_END_Date", "Expiry_Date"),
                    "exception_status": ("exception_status", "Exception_Status"),
                }
                data = {
                    field: self._source_value(raw, *source_keys)
                    for field, source_keys in aliases.items()
                }
                data = {field: value for field, value in data.items() if field in allowed_fields}
                data["report_published_date"] = self._source_datetime(data["report_published_date"])
                data["planned_remediation_date"] = self._source_datetime(data["planned_remediation_date"])
                data["risk_severity_change_date"] = self._source_datetime(data["risk_severity_change_date"])
                data["exception_end_date"] = self._source_datetime(data["exception_end_date"])
                data["cvss_score"] = self._source_number(data["cvss_score"])
                try:
                    data["plugin_id"] = int(data["plugin_id"]) if data["plugin_id"] is not None else None
                except (TypeError, ValueError):
                    data["plugin_id"] = None
                try:
                    data["port"] = int(data["port"]) if data["port"] is not None else None
                except (TypeError, ValueError):
                    data["port"] = None
                try:
                    data["ageing"] = int(data["ageing"]) if data["ageing"] is not None else None
                except (TypeError, ValueError):
                    data["ageing"] = None
                # Keep all original Squad1 BRD keys and values in PostgreSQL JSONB.
                data["source_payload"] = dict(raw)
                data["vulnerability_no"] = vuln_no
                if "target" not in data or not data["target"]:
                    data["target"] = "unknown-target"
                if "vulnerability_name" not in data or not data["vulnerability_name"]:
                    data["vulnerability_name"] = vuln_no

                clean_batch.append((vuln_no, data))
            except Exception:
                errors += 1

        # Process in chunks of 500
        chunk_size = 500
        for i in range(0, len(clean_batch), chunk_size):
            chunk = clean_batch[i : i + chunk_size]
            chunk_nos = [item[0] for item in chunk]

            try:
                existing_map = {
                    v.vulnerability_no: v
                    for v in self.db.query(Squad1Vulnerability)
                    .filter(Squad1Vulnerability.vulnerability_no.in_(chunk_nos))
                    .all()
                }

                for vuln_no, data in chunk:
                    existing = existing_map.get(vuln_no)
                    if existing is None:
                        record = Squad1Vulnerability(**data)
                        self.db.add(record)
                        created += 1
                    else:
                        for k, v in data.items():
                            setattr(existing, k, v)
                        updated += 1

                self.db.commit()

            except Exception:
                self.db.rollback()
                errors += len(chunk)

        return {
            "status": "completed",
            "records_received": len(raw_records),
            "records_created": created,
            "records_updated": updated,
            "exceptions_count": exceptions_count,
            "errors": errors,
        }
