"""Business logic for Red Hat Satellite resources and job simulation."""

from typing import Any

from sqlalchemy.orm import Session

from app.models.satellite import SatelliteJobHostResult
from app.repositories.satellite import (
    SatelliteHostRepository,
    SatelliteJobHostResultRepository,
    SatelliteJobRunRepository,
    SatelliteJobTemplateRepository,
)
from app.schemas.satellite import SatelliteJobLaunchRequest


class SatelliteService:
    """Coordinate Satellite resource operations and PostgreSQL persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.host_repository = SatelliteHostRepository(db)
        self.template_repository = SatelliteJobTemplateRepository(db)
        self.job_repository = SatelliteJobRunRepository(db)
        self.result_repository = SatelliteJobHostResultRepository(db)

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

        query = self.db.query(self.host_repository.model)
        total = query.count()

        items = (
            query
            .order_by(self.host_repository.model.id)
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

    def get_host(self, host_id: int) -> Any | None:
        """Retrieve a host using its internal database ID."""
        return self.host_repository.get_by_id(host_id)

    def find_hosts_by_ip(self, ip_address: str) -> list[Any]:
        """Return every stored host matching an IP address."""
        return self.host_repository.get_by_ip(ip_address)

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

        query = self.db.query(self.template_repository.model)
        total = query.count()

        items = (
            query
            .order_by(self.template_repository.model.id)
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

    def get_job_run(self, job_run_id: int) -> Any | None:
        """Retrieve a job run using its internal database ID."""
        return self.job_repository.get_by_id(job_run_id)

    def launch_simulated_job(
        self,
        payload: SatelliteJobLaunchRequest,
    ) -> dict[str, Any]:
        """Record a simulated job without executing remote commands.

        The supplied template and host IDs are external source IDs.
        This method resolves them to database records and stores the
        corresponding internal foreign keys.
        """
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
            host = self.host_repository.get_by_source_id(
                external_host_id
            )

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
                "job": job,
                "simulation": True,
                "message": (
                    "Simulated job request recorded; "
                    "no remote job was launched."
                ),
            }

        except Exception:
            self.db.rollback()
            raise