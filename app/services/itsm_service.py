"""Business logic for BMC Helix ITSM change requests and worklogs."""

from typing import Any

from sqlalchemy.orm import Session

from app.models.itsm import (
    ITSMChange,
    ITSMChangeHistory,
    ITSMWorklog,
)
from app.providers.factory import get_provider
from app.repositories.itsm import (
    ITSMChangeHistoryRepository,
    ITSMChangeRepository,
    ITSMWorklogRepository,
)
from app.schemas.itsm import (
    ITSMChangeCreate,
    ITSMChangeUpdate,
    ITSMWorklogCreate,
)


class ITSMService:
    """Coordinate ITSM change, worklog, and history operations."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ITSMChangeRepository(db)
        self.worklog_repository = ITSMWorklogRepository(db)
        self.history_repository = ITSMChangeHistoryRepository(db)
        self.provider = get_provider("itsm")

    @staticmethod
    def _validate_schedule(
        scheduled_start_at: Any | None,
        scheduled_end_at: Any | None,
    ) -> None:
        """Validate the scheduled window of a change request."""
        if (
            scheduled_start_at is not None
            and scheduled_end_at is not None
            and scheduled_end_at <= scheduled_start_at
        ):
            raise ValueError(
                "scheduled_end_at must be later than scheduled_start_at"
            )

    # ------------------------------------------------------------------
    # Change Request Operations (Database)
    # ------------------------------------------------------------------

    def list_changes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List persisted changes with optional status filtering."""
        if limit < 1 or limit > 50000:
            raise ValueError("limit must be between 1 and 50000")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        # Auto-import from active provider (API or JSON fixture) if database is empty
        if self.db.query(ITSMChange).count() == 0:
            self.import_provider_changes()

        query = self.db.query(ITSMChange)

        if status:
            query = query.filter(ITSMChange.status == status)

        total = query.count()

        items = (
            query.order_by(ITSMChange.id)
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

    def get_change(self, change_id: int) -> ITSMChange | None:
        """Retrieve a change request by its database ID."""
        return self.repository.get_by_id(change_id)

    def get_by_source_change_id(self, source_change_id: str) -> ITSMChange | None:
        """Retrieve a change request by external source change ID."""
        return self.repository.get_by_source_id(source_change_id)

    def create_change(self, payload: ITSMChangeCreate) -> ITSMChange:
        """Create a simulated change request in PostgreSQL."""
        data = payload.model_dump()

        self._validate_schedule(
            data.get("scheduled_start_at"),
            data.get("scheduled_end_at"),
        )

        source_id = data.get("source_change_id")
        try:
            if source_id:
                existing = self.repository.get_by_source_id(source_id)
                if existing is not None:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    self.db.commit()
                    self.db.refresh(existing)
                    return existing

            record = self.repository.create(data)

            # Record history entry for change creation
            history = ITSMChangeHistory(
                change_id=record.id,
                action="CREATE",
                new_status=record.status or "Draft",
                details="Change request created in system.",
                source_payload={"source_change_id": record.source_change_id},
            )
            self.db.add(history)

            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    def update_change(
        self,
        change_id: int,
        payload: ITSMChangeUpdate,
    ) -> ITSMChange | None:
        """Update selected fields of a persisted change request."""
        record = self.repository.get_by_id(change_id)

        if record is None:
            return None

        changes = payload.model_dump(exclude_unset=True)

        scheduled_start_at = changes.get(
            "scheduled_start_at",
            record.scheduled_start_at,
        )
        scheduled_end_at = changes.get(
            "scheduled_end_at",
            record.scheduled_end_at,
        )

        self._validate_schedule(
            scheduled_start_at,
            scheduled_end_at,
        )

        old_status = record.status
        new_status = changes.get("status", old_status)

        try:
            record = self.repository.update(record, changes)

            if old_status != new_status or changes:
                history = ITSMChangeHistory(
                    change_id=record.id,
                    action="UPDATE",
                    previous_status=old_status,
                    new_status=new_status,
                    details=f"Updated fields: {', '.join(sorted(changes.keys()))}",
                    source_payload=changes,
                )
                self.db.add(history)

            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Worklog Operations (Database)
    # ------------------------------------------------------------------

    def list_worklogs(
        self,
        *,
        change_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List worklogs with optional change_id filter."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        query = self.db.query(ITSMWorklog)
        if change_id is not None:
            query = query.filter(ITSMWorklog.change_id == change_id)

        total = query.count()
        items = query.order_by(ITSMWorklog.id).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    def get_worklog(self, worklog_id: int) -> ITSMWorklog | None:
        """Retrieve a worklog by internal ID."""
        return self.worklog_repository.get_by_id(worklog_id)

    def create_worklog(
        self,
        change_id: int,
        payload: ITSMWorklogCreate,
    ) -> ITSMWorklog:
        """Create a worklog entry associated with a change request."""
        change = self.repository.get_by_id(change_id)
        if change is None:
            raise ValueError(f"Change request {change_id} not found")

        data = payload.model_dump()
        data["change_id"] = change_id

        source_wid = data.get("source_worklog_id")
        try:
            if source_wid:
                existing = self.worklog_repository.get_by_source_id(source_wid)
                if existing is not None:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    self.db.commit()
                    self.db.refresh(existing)
                    return existing

            worklog = self.worklog_repository.create(data)
            self.db.commit()
            self.db.refresh(worklog)
            return worklog
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Change History Operations (Database)
    # ------------------------------------------------------------------

    def list_history(
        self,
        change_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List history entries for a change request."""
        query = self.db.query(ITSMChangeHistory).filter(ITSMChangeHistory.change_id == change_id)
        total = query.count()
        items = query.order_by(ITSMChangeHistory.id).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    # ------------------------------------------------------------------
    # Provider Operations (JSON Fixture or External ITSM API)
    # ------------------------------------------------------------------

    def list_provider_changes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List changes directly from the active provider (JSON or API)."""
        if hasattr(self.provider, "list_changes"):
            return self.provider.list_changes(limit=limit, offset=offset, filters=filters)
        return []

    def list_provider_worklogs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List worklogs directly from the active provider."""
        if hasattr(self.provider, "list_worklogs"):
            return self.provider.list_worklogs(limit=limit, offset=offset, filters=filters)
        return []

    def create_provider_change(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a change in the active provider."""
        if hasattr(self.provider, "create_change"):
            return self.provider.create_change(payload)
        raise ValueError("Active provider does not support creating changes")

    def import_provider_changes(self) -> dict[str, Any]:
        """Import changes and worklogs from provider into PostgreSQL."""
        changes_imported = 0
        worklogs_imported = 0
        errors = 0

        # Import changes in batches
        if hasattr(self.provider, "list_changes"):
            try:
                raw_changes = self.provider.list_changes(limit=50000)
                clean_changes: dict[str, dict[str, Any]] = {}
                for item in raw_changes:
                    sid = str(item.get("source_change_id") or item.get("id") or "").strip()
                    if sid:
                        clean_changes[sid] = item

                chunk = list(clean_changes.values())
                chunk_size = 500
                for i in range(0, len(chunk), chunk_size):
                    batch = chunk[i : i + chunk_size]
                    batch_ids = [str(item.get("source_change_id") or item.get("id")).strip() for item in batch]
                    existing_map = {
                        c.source_change_id: c
                        for c in self.db.query(ITSMChange).filter(ITSMChange.source_change_id.in_(batch_ids)).all()
                    }
                    for item in batch:
                        source_id = str(item.get("source_change_id") or item.get("id")).strip()
                        existing = existing_map.get(source_id)
                        data = {
                            "source_change_id": source_id,
                            "first_name": item.get("first_name"),
                            "last_name": item.get("last_name"),
                            "status": item.get("status"),
                            "impact": str(item.get("impact")) if item.get("impact") is not None else None,
                            "urgency": str(item.get("urgency")) if item.get("urgency") is not None else None,
                            "location_company": item.get("location_company"),
                            "detailed_description": item.get("detailed_description"),
                            "company": item.get("company"),
                            "support_organization": item.get("support_organization"),
                            "support_group_name": item.get("support_group_name"),
                            "change_nature": item.get("change_nature"),
                            "nature_of_change": item.get("nature_of_change"),
                            "application_infrastructure": item.get("application_infrastructure"),
                            "downtime_required": item.get("downtime_required"),
                            "service_ci": item.get("service_ci"),
                            "description": item.get("description"),
                            "environment": item.get("environment"),
                            "scheduled_start_at": item.get("scheduled_start_at"),
                            "scheduled_end_at": item.get("scheduled_end_at"),
                            "source_payload": item.get("source_payload") or item,
                        }
                        if existing is None:
                            self.repository.create(data)
                        else:
                            self.repository.update(existing, data)
                        changes_imported += 1
                    self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        # Import worklogs
        if hasattr(self.provider, "list_worklogs"):
            try:
                for item in self.provider.list_worklogs(limit=5000):
                    source_wid = str(item.get("source_worklog_id") or item.get("id") or "").strip()
                    change_ref = item.get("change_id") or item.get("source_change_id")
                    change = None
                    if change_ref:
                        change = self.repository.get_by_source_id(str(change_ref))
                    if not change:
                        # Link to first change if any
                        first_change = self.db.query(ITSMChange).first()
                        if first_change:
                            change = first_change

                    if change and source_wid:
                        existing_w = self.worklog_repository.get_by_source_id(source_wid)
                        wdata = {
                            "change_id": change.id,
                            "source_worklog_id": source_wid,
                            "worklog_type": item.get("worklog_type") or "General Information",
                            "description": item.get("description") or "Imported worklog",
                            "submitter": item.get("submitter"),
                            "source_payload": item.get("source_payload") or item,
                        }
                        if existing_w is None:
                            self.worklog_repository.create(wdata)
                            worklogs_imported += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        return {
            "changes_imported": changes_imported,
            "worklogs_imported": worklogs_imported,
            "errors": errors,
        }