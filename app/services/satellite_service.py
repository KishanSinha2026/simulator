"""Business logic for Red Hat Satellite hosts and job runs."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories.satellite import (
    SatelliteHostRepository,
    SatelliteJobRunRepository,
    SatelliteJobTemplateRepository,
)
from app.schemas.satellite import SatelliteJobLaunchRequest


class SatelliteService:
    """Coordinate Satellite resource operations and database persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.host_repository = SatelliteHostRepository(db)
        self.template_repository = SatelliteJobTemplateRepository(db)
        self.job_repository = SatelliteJobRunRepository(db)

    def list_hosts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List hosts stored in PostgreSQL."""
        query = self.db.query(self.host_repository.model)
        total = query.count()
        items = (
            query.order_by(self.host_repository.model.id)
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

    def get_host(self, host_id: int) -> Any:
        """Retrieve a host by database ID."""
        return self.host_repository.get_by_id(host_id)

    def find_hosts_by_ip(self, ip_address: str) -> list[Any]:
        """Return every host matching an IP address."""
        return self.host_repository.get_by_ip(ip_address)

    def list_job_templates(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List job templates stored in PostgreSQL."""
        query = self.db.query(self.template_repository.model)
        total = query.count()
        items = (
            query.order_by(self.template_repository.model.id)
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

    def get_job_run(self, job_run_id: int) -> Any:
        """Retrieve a job run by database ID."""
        return self.job_repository.get_by_id(job_run_id)

    def launch_simulated_job(
        self,
        payload: SatelliteJobLaunchRequest,
    ) -> dict[str, Any]:
        """Validate and record a simulated job request.

        This method deliberately does not launch a real Satellite job.
        Live execution requires a separate, explicitly authorized workflow.
        """
        if not payload.host_ids:
            raise ValueError("At least one host ID is required")

        if len(set(payload.host_ids)) != len(payload.host_ids):
            raise ValueError("Duplicate host IDs are not allowed")

        template = self.template_repository.get_by_source_id(
            payload.template_id
        )
        if template is None:
            raise ValueError("Job template was not found in PostgreSQL")

        try:
            job = self.job_repository.create(
                {
                    "template_id": payload.template_id,
                    "status": "pending",
                    "source_payload": {
                        "host_ids": payload.host_ids,
                        "inputs": payload.inputs,
                        "simulation": True,
                    },
                }
            )
            self.db.commit()
            self.db.refresh(job)
            return {
                "job": job,
                "simulation": True,
                "message": "Simulated job request recorded; no remote job was launched.",
            }
        except Exception:
            self.db.rollback()
            raise