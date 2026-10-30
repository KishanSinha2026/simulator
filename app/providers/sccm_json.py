"""JSON fixture provider for SCCM 2509 Windows execution simulation."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.providers.json_provider import JsonProvider


class SCCMJsonProvider:
    """Read and manage simulated SCCM records in JSON files."""

    def __init__(self) -> None:
        self.devices = JsonProvider("sccm/devices.json")
        self.collections = JsonProvider("sccm/collections.json")
        self.deployments = JsonProvider("sccm/deployments.json")
        self.deployment_runs = JsonProvider("sccm/deployment_runs.json")

    def list_devices(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List devices with optional filters and pagination."""
        if not 1 <= limit <= 50000:
            raise ValueError("limit must be between 1 and 50000")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        return self.devices.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def get_device(self, resource_id: str) -> dict[str, Any] | None:
        """Find device by ResourceID."""
        norm_id = resource_id.strip()
        for dev in self.devices.list_records(limit=50000):
            if dev.get("resource_id", "").strip() == norm_id:
                return dev
        return None

    def list_collections(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List approved device collections."""
        return self.collections.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def get_collection(self, collection_id: str) -> dict[str, Any] | None:
        """Find collection by CollectionID."""
        norm_id = collection_id.strip()
        for col in self.collections.list_records(limit=50000):
            if col.get("collection_id", "").strip() == norm_id:
                return col
        return None

    def list_deployments(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List update group deployment policies."""
        return self.deployments.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def get_deployment(self, assignment_id: str) -> dict[str, Any] | None:
        """Find deployment policy by AssignmentID."""
        norm_id = assignment_id.strip()
        for dep in self.deployments.list_records(limit=50000):
            if dep.get("assignment_id", "").strip() == norm_id:
                return dep
        return None

    def get_deployment_run(self, run_id: str) -> dict[str, Any] | None:
        """Find deployment run by run_id."""
        norm_id = run_id.strip()
        for run in self.deployment_runs.list_records(limit=50000):
            if run.get("run_id", "").strip() == norm_id:
                return run
        return None

    def launch_deployment(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record a simulated patch deployment execution matching BRD Section 8.5.5."""
        data = dict(payload)
        run_id = str(data.get("run_id", "")).strip() or f"RUN-WIN-{uuid4().hex[:6].upper()}"
        data["run_id"] = run_id

        # Resolve targets and generate asset details
        targets = data.get("targets") or []
        asset_details = []
        now_iso = datetime.now(timezone.utc).isoformat()

        compliant_count = 0
        error_count = 0
        unknown_count = 0

        for t in targets:
            res_id = t.get("resource_id", "RES-UNKNOWN")
            hostname = t.get("hostname", "unknown-host")
            ci_id = t.get("server_ci_id")

            # Check client active readiness
            dev = self.get_device(res_id)
            is_active = bool(
                dev
                and dev.get("client_active_status", False)
                and dev.get("is_client", False)
            )

            if dev is None:
                status_val = "Unknown"
                unknown_count += 1
            elif is_active:
                status_val = "Compliant"
                compliant_count += 1
            else:
                status_val = "Error"
                error_count += 1

            asset_details.append({
                "resource_id": res_id,
                "server_ci_id": ci_id,
                "hostname": hostname,
                "status": status_val,
                "status_type": (
                    "Success" if is_active
                    else "DeviceNotFound" if dev is None
                    else "ClientInactive"
                ),
                "error_code": (
                    "0" if is_active
                    else "DEVICE_NOT_FOUND" if dev is None
                    else "0x87D00324"
                ),
                "status_time": now_iso,
            })

        record = {
            "id": f"sccm-run-{uuid4().hex[:6]}",
            "run_id": run_id,
            "change_number": data.get("change_number", ""),
            "mode": data.get("mode", "STANDARD_PATCH"),
            "target_collection_id": data.get("target_collection_id", ""),
            "assignment_id": data.get("assignment_id", ""),
            "window_start": data.get("window_start"),
            "window_end": data.get("window_end"),
            "reboot_policy": data.get("reboot_policy", "CLIENT_APPROVED"),
            "status": "completed",
            "compliant_count": compliant_count,
            "in_progress_count": 0,
            "error_count": error_count,
            "unknown_count": unknown_count,
            "skipped_count": 0,
            "started_at": now_iso,
            "completed_at": now_iso,
            "asset_details": asset_details,
            "source_payload": {"is_simulated": True},
        }

        # Idempotently upsert by run_id
        existing = self.get_deployment_run(run_id)
        if existing is not None:
            record["id"] = existing["id"]
            return self.deployment_runs.update_record(existing["id"], record)

        return self.deployment_runs.create_record(record)
