"""JSON fixture provider for Red Hat Satellite simulation."""

from typing import Any
from uuid import uuid4

from app.providers.json_provider import JsonProvider


class SatelliteJsonProvider:
    """Read and manage simulated Satellite records in JSON files."""

    def __init__(self) -> None:
        self.hosts = JsonProvider("satellite/hosts.json")
        self.job_templates = JsonProvider(
            "satellite/job_templates.json"
        )
        self.job_runs = JsonProvider("satellite/job_runs.json")
        self.host_results = JsonProvider(
            "satellite/job_host_results.json"
        )

    def get_host(
        self,
        host_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a host by its fixture ID."""
        return self.hosts.get_by_id(host_id)

    def list_hosts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List hosts with optional filters and pagination."""
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
        """List available simulated job templates."""
        return self.job_templates.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def get_job_run(
        self,
        job_run_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a job run by its fixture ID."""
        return self.job_runs.get_by_id(job_run_id)

    def list_job_runs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List job runs with optional filters and pagination."""
        return self.job_runs.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def list_host_results(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List simulated per-host results."""
        return self.host_results.list_records(
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
        """Record a simulated job without executing remote commands."""
        if not host_ids:
            raise ValueError("At least one host is required")

        if len(set(host_ids)) != len(host_ids):
            raise ValueError("Duplicate host IDs are not allowed")

        template = self.job_templates.get_by_id(template_id)

        if template is None:
            raise ValueError(
                f"Satellite job template {template_id!r} was not found"
            )

        hosts: list[dict[str, Any]] = []

        for host_id in host_ids:
            host = self.hosts.get_by_id(host_id)

            if host is None:
                raise ValueError(
                    f"Satellite host {host_id!r} was not found"
                )

            hosts.append(host)

        job_run_id = f"SIM-JOB-{uuid4().hex[:12]}"

        job_run = {
            "id": job_run_id,
            "job_template_id": template_id,
            "job_template_name": template.get("name"),
            "host_ids": [str(host["id"]) for host in hosts],
            "status": "pending",
            "started_at": None,
            "finished_at": None,
            "result_summary": (
                "Simulation queued; no remote command was executed."
            ),
            "inputs": inputs or {},
            "is_simulated": True,
            "change_id": None,
            "error_message": None,
        }

        # Create the run first, then create one result per host.
        self.job_runs.create_record(job_run)

        try:
            for host in hosts:
                self.host_results.create_record(
                    {
                        "id": f"{job_run_id}-{host['id']}",
                        "job_run_id": job_run_id,
                        "host_id": str(host["id"]),
                        "status": "pending",
                        "started_at": None,
                        "finished_at": None,
                        "exit_code": None,
                        "stdout": (
                            "Simulation queued; no command executed."
                        ),
                        "stderr": "",
                        "is_simulated": True,
                    }
                )
        except Exception:
            # Avoid leaving an apparently valid run if result creation fails.
            records = self.job_runs._read_records()
            records = [
                record
                for record in records
                if str(record.get("id")) != job_run_id
            ]
            self.job_runs._write_records(records)
            raise

        return job_run

    def cancel_job(
        self,
        job_run_id: str,
    ) -> dict[str, Any]:
        """Cancel a pending simulated job without contacting Satellite."""
        records = self.job_runs._read_records()

        for record in records:
            if str(record.get("id")) != str(job_run_id):
                continue

            if record.get("status") != "pending":
                raise ValueError(
                    "Only pending simulated jobs can be cancelled"
                )

            record["status"] = "cancelled"
            record["result_summary"] = (
                "Simulated job cancelled; no remote command executed."
            )

            self.job_runs._write_records(records)

            # Mark associated pending host results as cancelled.
            result_records = self.host_results._read_records()

            for result in result_records:
                if (
                    str(result.get("job_run_id")) == str(job_run_id)
                    and result.get("status") == "pending"
                ):
                    result["status"] = "cancelled"
                    result["stdout"] = (
                        "Simulation cancelled; no command executed."
                    )

            self.host_results._write_records(result_records)

            return record

        raise ValueError(
            f"Satellite job run {job_run_id!r} was not found"
        )

    def create_host(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a simulated host in the JSON fixture."""
        if not payload:
            raise ValueError("Payload cannot be empty")
        record = dict(payload)
        source_id = record.get("source_host_id")
        if not source_id or not str(source_id).strip():
            raise ValueError("source_host_id is required")
        record["source_host_id"] = str(source_id).strip()
        record.setdefault("id", record["source_host_id"])
        return self.hosts.create_record(record)

    def create_job_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a simulated job template in the JSON fixture."""
        if not payload:
            raise ValueError("Payload cannot be empty")
        record = dict(payload)
        source_id = record.get("source_template_id")
        if not source_id or not str(source_id).strip():
            raise ValueError("source_template_id is required")
        record["source_template_id"] = str(source_id).strip()
        record.setdefault("id", record["source_template_id"])
        return self.job_templates.create_record(record)