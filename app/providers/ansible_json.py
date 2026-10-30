"""Read-only Ansible fixtures and safe simulated execution fallback."""

from typing import Any
from uuid import uuid4

from app.providers.json_provider import JsonProvider


class AnsibleJsonProvider:
    """Provide fixture templates without running commands on any host."""

    def __init__(self) -> None:
        self.templates = JsonProvider("ansible/job_templates.json")

    def list_templates(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        if not 1 <= limit <= 50000 or offset < 0:
            raise ValueError("limit must be between 1 and 50000 and offset cannot be negative")
        records = self.templates.list_records(limit=limit, offset=offset)
        total = len(self.templates.list_records(limit=50000))
        next_offset = offset + len(records)
        return {
            "results": records,
            "count": total,
            "next": f"?offset={next_offset}" if next_offset < total else None,
        }

    def test_connection(self) -> dict[str, Any]:
        return {
            "connected": False,
            "name": "Ansible JSON fixture fallback",
            "version": None,
            "provider_mode": "json",
            "fallback_reason": "AAP API is unavailable; fixture mode is active",
        }

    def launch_job(
        self,
        template_id: str,
        *,
        limit: str | None,
        extra_vars: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a simulated operation; never execute host changes in fixture mode."""
        template = self.templates.get_by_id(template_id)
        if template is None:
            raise ValueError(f"Ansible fixture template {template_id!r} was not found")
        job_id = f"SIM-{uuid4().hex[:12].upper()}"
        return {
            "id": job_id,
            "status": "simulated",
            "started": None,
            "finished": None,
            "template_id": template_id,
            "limit": limit,
            "extra_vars": extra_vars,
            "provider_mode": "json",
            "is_simulated": True,
        }

    def get_job(self, job_id: str) -> dict[str, Any]:
        if not job_id.startswith("SIM-"):
            raise RuntimeError("Live AAP job status is unavailable while the controller is offline")
        return {"id": job_id, "status": "simulated", "provider_mode": "json", "is_simulated": True}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        if not job_id.startswith("SIM-"):
            raise RuntimeError("Live AAP job cancellation is unavailable while the controller is offline")
        return {"id": job_id, "status": "simulated_cancelled", "provider_mode": "json", "is_simulated": True}


