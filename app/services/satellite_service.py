"""Business logic for Red Hat Satellite resources and job simulation."""

from typing import Any

from sqlalchemy.orm import Session

from app.models.satellite import (
    SatelliteHost,
    SatelliteJobHostResult,
    SatelliteJobRun,
    SatelliteJobTemplate,
)
from app.providers.factory import get_provider
from app.repositories.satellite import (
    SatelliteHostRepository,
    SatelliteJobHostResultRepository,
    SatelliteJobRunRepository,
    SatelliteJobTemplateRepository,
)
from app.schemas.satellite import (
    SatelliteHostCreate,
    SatelliteHostUpdate,
    SatelliteJobCancelRequest,
    SatelliteJobLaunchRequest,
    SatelliteJobTemplateCreate,
)


class SatelliteService:
    """Coordinate Satellite resource operations and PostgreSQL persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.host_repository = SatelliteHostRepository(db)
        self.template_repository = SatelliteJobTemplateRepository(db)
        self.job_repository = SatelliteJobRunRepository(db)
        self.result_repository = SatelliteJobHostResultRepository(db)
        self.provider = get_provider("satellite")

    # ------------------------------------------------------------------
    # Host Operations (Database)
    # ------------------------------------------------------------------

    def list_hosts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List hosts stored in PostgreSQL."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        query = self.db.query(SatelliteHost)
        total = query.count()

        items = (
            query.order_by(SatelliteHost.id)
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

    def get_host(self, host_id: int) -> SatelliteHost | None:
        """Retrieve a host using its internal database ID."""
        return self.host_repository.get_by_id(host_id)

    def find_hosts_by_ip(self, ip_address: str) -> list[SatelliteHost]:
        """Return every stored host matching an IP address."""
        return self.host_repository.get_by_ip(ip_address)

    def create_host(self, payload: SatelliteHostCreate) -> SatelliteHost:
        """Create a Satellite host record in PostgreSQL."""
        data = payload.model_dump()
        try:
            host = self.host_repository.create(data)
            self.db.commit()
            self.db.refresh(host)
            return host
        except Exception:
            self.db.rollback()
            raise

    def update_host(
        self,
        host_id: int,
        payload: SatelliteHostUpdate,
    ) -> SatelliteHost | None:
        """Update selected fields on a Satellite host."""
        host = self.host_repository.get_by_id(host_id)
        if host is None:
            return None

        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("At least one field must be supplied")

        try:
            host = self.host_repository.update(host, changes)
            self.db.commit()
            self.db.refresh(host)
            return host
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Job Template Operations (Database)
    # ------------------------------------------------------------------

    def list_job_templates(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List job templates stored in PostgreSQL."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        query = self.db.query(SatelliteJobTemplate)
        total = query.count()

        items = (
            query.order_by(SatelliteJobTemplate.id)
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

    def get_job_template(self, template_id: int) -> SatelliteJobTemplate | None:
        """Retrieve a job template by internal database ID."""
        return self.template_repository.get_by_id(template_id)

    def create_job_template(
        self,
        payload: SatelliteJobTemplateCreate,
    ) -> SatelliteJobTemplate:
        """Create a job template in PostgreSQL."""
        data = payload.model_dump()
        try:
            template = self.template_repository.create(data)
            self.db.commit()
            self.db.refresh(template)
            return template
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Job Run & Execution Operations (Database)
    # ------------------------------------------------------------------

    def list_job_runs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List job runs stored in PostgreSQL."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        query = self.db.query(SatelliteJobRun)
        if status:
            query = query.filter(SatelliteJobRun.status == status)

        total = query.count()
        items = query.order_by(SatelliteJobRun.id.desc()).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    def get_job_run(self, job_run_id: int) -> SatelliteJobRun | None:
        """Retrieve a job run using its internal database ID."""
        return self.job_repository.get_by_id(job_run_id)

    def launch_simulated_job(
        self,
        payload: SatelliteJobLaunchRequest,
    ) -> dict[str, Any]:
        """Record a simulated job without executing remote commands."""
        if not payload.host_ids:
            raise ValueError("At least one host ID is required")

        if len(set(payload.host_ids)) != len(payload.host_ids):
            raise ValueError("Duplicate host IDs are not allowed")

        template = self.template_repository.get_by_source_id(
            payload.template_id
        )

        if template is None:
            raise ValueError(
                f"Satellite job template {payload.template_id!r} "
                "was not found in PostgreSQL"
            )

        hosts = []

        for external_host_id in payload.host_ids:
            host = self.host_repository.get_by_source_id(external_host_id)

            if host is None:
                raise ValueError(
                    f"Satellite host {external_host_id!r} "
                    "was not found in PostgreSQL"
                )

            hosts.append(host)

        try:
            job = self.job_repository.create(
                {
                    "template_id": template.id,
                    "status": "pending",
                    "inputs": payload.inputs,
                    "source_payload": {
                        "external_template_id": payload.template_id,
                        "external_host_ids": payload.host_ids,
                        "simulation": True,
                    },
                }
            )

            # Create an initial result for every selected host.
            for host in hosts:
                result = SatelliteJobHostResult(
                    job_run_id=job.id,
                    host_id=host.id,
                    status="pending",
                    result_text=(
                        "Simulation queued; no remote command executed."
                    ),
                    source_payload={
                        "is_simulated": True,
                        "external_host_id": host.source_host_id,
                    },
                )
                self.db.add(result)

            self.db.commit()
            self.db.refresh(job)

            return {
                "id": job.id,
                "job_id": job.id,
                "template_id": job.template_id,
                "status": job.status,
                "simulation": True,
                "message": (
                    "Simulated job request recorded; "
                    "no remote job was launched."
                ),
            }

        except Exception:
            self.db.rollback()
            raise

    def cancel_job_run(
        self,
        job_run_id: int,
        payload: SatelliteJobCancelRequest,
    ) -> SatelliteJobRun:
        """Cancel a pending simulated job run."""
        job = self.job_repository.get_by_id(job_run_id)
        if job is None:
            raise ValueError(f"Satellite job run {job_run_id} not found")

        if job.status != "pending":
            raise ValueError("Only pending jobs can be cancelled")

        try:
            job.status = "cancelled"
            job.source_payload = job.source_payload or {}
            job.source_payload["cancellation_reason"] = payload.reason

            # Also update host results
            host_results = self.result_repository.list_by_job_run_id(job.id)
            for res in host_results:
                if res.status == "pending":
                    res.status = "cancelled"
                    res.result_text = f"Cancelled: {payload.reason or 'User requested cancellation'}"

            self.db.commit()
            self.db.refresh(job)
            return job
        except Exception:
            self.db.rollback()
            raise

    def list_host_results(
        self,
        job_run_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List host results for a job run."""
        query = self.db.query(SatelliteJobHostResult).filter(SatelliteJobHostResult.job_run_id == job_run_id)
        total = query.count()
        items = query.order_by(SatelliteJobHostResult.id).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    def get_host_result(
        self,
        job_run_id: int,
        host_id: int,
    ) -> SatelliteJobHostResult | None:
        """Retrieve host result by job run and host ID."""
        return self.result_repository.get_for_job_and_host(job_run_id, host_id)

    # ------------------------------------------------------------------
    # Provider Operations (JSON Fixture or External Satellite API)
    # ------------------------------------------------------------------

    def list_provider_hosts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List hosts from the active Satellite provider."""
        if hasattr(self.provider, "list_hosts"):
            return self.provider.list_hosts(limit=limit, offset=offset, filters=filters)
        return []

    def list_provider_job_templates(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List job templates from the active Satellite provider."""
        if hasattr(self.provider, "list_job_templates"):
            return self.provider.list_job_templates(limit=limit, offset=offset, filters=filters)
        return []

    def list_provider_job_runs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List job runs from the active Satellite provider."""
        if hasattr(self.provider, "list_job_runs"):
            return self.provider.list_job_runs(limit=limit, offset=offset, filters=filters)
        return []

    def create_provider_host(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a host in the active JSON provider."""
        if hasattr(self.provider, "create_host"):
            return self.provider.create_host(payload)
        raise ValueError("Active provider does not support creating hosts")

    def launch_provider_job(
        self,
        *,
        template_id: str,
        host_ids: list[str],
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Launch job directly via provider."""
        if hasattr(self.provider, "launch_job"):
            return self.provider.launch_job(
                template_id=template_id,
                host_ids=host_ids,
                inputs=inputs,
            )
        raise ValueError("Active provider does not support job launching")

    def cancel_provider_job(self, job_run_id: str) -> dict[str, Any]:
        """Cancel job directly via provider."""
        if hasattr(self.provider, "cancel_job"):
            return self.provider.cancel_job(job_run_id)
        raise ValueError("Active provider does not support job cancellation")

    def import_provider_data(self) -> dict[str, Any]:
        """Import hosts and job templates from provider into PostgreSQL."""
        hosts_imported = 0
        templates_imported = 0
        errors = 0

        # Import hosts
        if hasattr(self.provider, "list_hosts"):
            try:
                for item in self.provider.list_hosts(limit=5000):
                    source_id = str(item.get("source_host_id") or item.get("id") or "").strip()
                    if not source_id:
                        continue
                    existing = self.host_repository.get_by_source_id(source_id)
                    data = {
                        "source_host_id": source_id,
                        "name": item.get("name") or source_id,
                        "ip_address": item.get("ip_address"),
                        "operating_system": item.get("operating_system"),
                        "organization_id": item.get("organization_id"),
                        "location_id": item.get("location_id"),
                        "source_payload": item.get("source_payload") or item,
                    }
                    if existing is None:
                        self.host_repository.create(data)
                        hosts_imported += 1
                    else:
                        self.host_repository.update(existing, data)
                        hosts_imported += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        # Import job templates
        if hasattr(self.provider, "list_job_templates"):
            try:
                for item in self.provider.list_job_templates(limit=5000):
                    source_id = str(item.get("source_template_id") or item.get("id") or "").strip()
                    if not source_id:
                        continue
                    existing = self.template_repository.get_by_source_id(source_id)
                    data = {
                        "source_template_id": source_id,
                        "name": item.get("name") or source_id,
                        "description": item.get("description"),
                        "template_type": item.get("template_type"),
                        "input_schema": item.get("input_schema"),
                        "source_payload": item.get("source_payload") or item,
                    }
                    if existing is None:
                        self.template_repository.create(data)
                        templates_imported += 1
                    else:
                        self.template_repository.update(existing, data)
                        templates_imported += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        return {
            "hosts_imported": hosts_imported,
            "job_templates_imported": templates_imported,
            "errors": errors,
        }