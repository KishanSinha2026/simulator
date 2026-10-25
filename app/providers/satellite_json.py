
from typing import Any
from uuid import uuid4

from app.providers.json_provider import JsonProvider


class SatelliteJsonProvider:
    """Red Hat Satellite simulator backed by local JSON fixtures."""

    def __init__(self) -> None:
        self.hosts = JsonProvider("satellite/hosts.json")
        self.job_templates = JsonProvider("satellite/job_templates.json")
        self.job_runs = JsonProvider("satellite/job_runs.json")
        self.host_results = JsonProvider("satellite/host_results.json")

    def get_host(self, host_id: str) -> dict[str, Any] | None:
        return self.hosts.get_by_id(host_id)

    def list_hosts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.hosts.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def list_job_templates(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.job_templates.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def get_job_run(self, job_run_id: str) -> dict[str, Any] | None:
        return self.job_runs.get_by_id(job_run_id)

    def list_job_runs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.job_runs.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def launch_job(
        self,
        *,
        template_id: str,
        host_ids: list[str],
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not host_ids:
            raise ValueError("At least one host is required")

        template = self.job_templates.get_by_id(template_id)
        if template is None:
            raise ValueError(
                f"Satellite job template {template_id!r} was not found"
            )

        hosts = []
        for host_id in host_ids:
            host = self.hosts.get_by_id(host_id)
            if host is None:
                raise ValueError(f"Satellite host {host_id!r} was not found")
            hosts.append(host)

        job_run_id = f"SIM-JOB-{uuid4().hex[:12]}"
        job_run = {
            "id": job_run_id,
            "template_id": template_id,
            "host_ids": host_ids,
            "inputs": inputs or {},
            "status": "pending",
            "simulated": True,
        }

        self.job_runs.create_record(job_run)

        for host in hosts:
            self.host_results.create_record(
                {
                    "id": f"{job_run_id}-{host['id']}",
                    "job_run_id": job_run_id,
                    "host_id": host["id"],
                    "status": "pending",
                    "output": "Simulation queued; no command executed.",
                }
            )

        return job_run

    def cancel_job(self, job_run_id: str) -> dict[str, Any]:
        """Cancel a pending simulated job; never contact a live server."""
        records = self.job_runs._read_records()

        for record in records:
            if str(record.get("id")) == str(job_run_id):
                if record.get("status") != "pending":
                    raise ValueError(
                        "Only pending simulated jobs can be cancelled"
                    )

                record["status"] = "cancelled"
                self.job_runs._write_records(records)
                return record

        raise ValueError(f"Satellite job run {job_run_id!r} was not found")
