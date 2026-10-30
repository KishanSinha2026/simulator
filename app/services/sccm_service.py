"""Business logic for SCCM 2509 Windows execution and patch deployments."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.sccm import (
    SCCMCollection,
    SCCMDeployment,
    SCCMDeploymentAssetDetail,
    SCCMDeploymentRun,
    SCCMDevice,
)
from app.repositories.sccm import (
    SCCMCollectionRepository,
    SCCMDeploymentRepository,
    SCCMDeploymentRunRepository,
    SCCMDeviceRepository,
)
from app.schemas.sccm import SCCMJobLaunchRequest
from app.services.patching_guard import active_exception_targets


class SCCMService:
    """Coordinate SCCM device inventory, collection targeting, and guarded patch jobs."""

    def __init__(self, db: Session, provider: Any) -> None:
        self.db = db
        self.device_repo = SCCMDeviceRepository(db)
        self.collection_repo = SCCMCollectionRepository(db)
        self.deployment_repo = SCCMDeploymentRepository(db)
        self.run_repo = SCCMDeploymentRunRepository(db)
        self.provider = provider

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        """Validate pagination parameters."""
        if not 1 <= limit <= 50000:
            raise ValueError("limit must be between 1 and 50000")
        if offset < 0:
            raise ValueError("offset cannot be negative")

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    # ------------------------------------------------------------------
    # Devices (Table 20: SMS_CombinedDeviceResources)
    # ------------------------------------------------------------------

    def list_devices(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        collection_id: str | None = None,
    ) -> dict[str, Any]:
        """List devices and readiness activity."""
        self._validate_pagination(limit, offset)

        if self.db.query(SCCMDevice).count() == 0:
            self.import_provider_data()

        query = self.db.query(SCCMDevice)
        if collection_id:
            query = query.filter(SCCMDevice.collection_id == collection_id.strip())

        total = query.count()
        items = query.order_by(SCCMDevice.id).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    def get_device(self, device_id: int) -> SCCMDevice | None:
        """Retrieve a device by internal database ID."""
        if device_id < 1:
            raise ValueError("device_id must be greater than zero")
        return self.device_repo.get_by_id(device_id)

    # ------------------------------------------------------------------
    # Collections (Table 20: SMS_Collection)
    # ------------------------------------------------------------------

    def list_collections(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List approved device collections."""
        self._validate_pagination(limit, offset)

        if self.db.query(SCCMCollection).count() == 0:
            self.import_provider_data()

        query = self.db.query(SCCMCollection)
        total = query.count()
        items = query.order_by(SCCMCollection.id).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    def get_collection(self, collection_id: str) -> SCCMCollection | None:
        """Retrieve a collection by external CollectionID."""
        return self.collection_repo.get_by_collection_id(collection_id)

    # ------------------------------------------------------------------
    # Deployments (Table 20: SMS_UpdateGroupAssignment)
    # ------------------------------------------------------------------

    def list_deployments(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List software update group deployment policies."""
        self._validate_pagination(limit, offset)

        if self.db.query(SCCMDeployment).count() == 0:
            self.import_provider_data()

        query = self.db.query(SCCMDeployment)
        total = query.count()
        items = query.order_by(SCCMDeployment.id).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    # ------------------------------------------------------------------
    # Deployment Runs (BRD Section 8.5.5 Guarded Patch Job)
    # ------------------------------------------------------------------

    def launch_deployment_run(
        self,
        payload: SCCMJobLaunchRequest,
    ) -> SCCMDeploymentRun:
        """Launch and record a guarded patch deployment execution run."""
        data = payload.model_dump()
        run_id = str(data.get("run_id") or "").strip()
        if not run_id:
            run_id = f"RUN-WIN-{uuid4().hex[:6].upper()}"

        deployment: SCCMDeployment | None = None
        external_deployment_id = str(data.get("deployment_id") or "").strip()
        assignment_id = str(data.get("assignment_id") or "").strip()
        if external_deployment_id:
            for candidate in self.db.query(SCCMDeployment).all():
                source_id = str((candidate.source_payload or {}).get("id") or "")
                if external_deployment_id in {
                    str(candidate.id), candidate.assignment_id, source_id,
                }:
                    deployment = candidate
                    break
        elif assignment_id:
            deployment = self.deployment_repo.get_by_assignment_id(assignment_id)
        if deployment is None:
            raise ValueError("SCCM deployment was not found in the imported deployment inventory")

        if assignment_id and assignment_id != deployment.assignment_id:
            raise ValueError("assignment_id does not match the selected deployment")
        assignment_id = deployment.assignment_id
        target_collection_id = str(data.get("target_collection_id") or deployment.target_collection_id)
        if target_collection_id != deployment.target_collection_id:
            raise ValueError("target_collection_id does not match the selected deployment")
        external_deployment_id = external_deployment_id or str(
            (deployment.source_payload or {}).get("id") or deployment.id
        )

        targets = data.get("targets") or []
        if not targets:
            raise ValueError("targets list cannot be empty")

        # Check existing run for idempotency
        existing_run = self.run_repo.get_by_run_id(run_id)
        if existing_run is not None:
            return existing_run

        now = datetime.now(timezone.utc)
        compliant_count = 0
        error_count = 0
        unknown_count = 0
        skipped_count = 0

        asset_details_to_create = []
        target_devices: list[tuple[dict[str, Any], SCCMDevice | None]] = []
        exception_candidates: set[str] = set()
        for target in targets:
            resource_id = str(target.get("resource_id", "")).strip()
            hostname = str(target.get("hostname", "")).strip()
            device = self.device_repo.get_by_resource_id(resource_id)
            if device and device.collection_id and device.collection_id != target_collection_id:
                raise ValueError(
                    f"Target {hostname or resource_id!r} is outside the deployment collection"
                )
            target_devices.append((target, device))
            exception_candidates.update(value for value in (
                resource_id,
                hostname,
                device.name if device else None,
                device.ip_address if device else None,
            ) if value)
        exception_targets = active_exception_targets(self.db, exception_candidates)

        for target, device in target_devices:
            res_id = str(target.get("resource_id", "")).strip()
            hostname = str(target.get("hostname", "")).strip()
            ci_id = target.get("server_ci_id")

            # Check client active readiness gate
            is_active = bool(device and device.client_active_status and device.is_client)
            has_active_exception = any(
                value and value.strip().casefold() in exception_targets
                for value in (res_id, hostname, device.name if device else None, device.ip_address if device else None)
            )

            if device is None:
                status_val = "Unknown"
                unknown_count += 1
            elif has_active_exception:
                status_val = "Skipped"
                skipped_count += 1
            elif is_active:
                status_val = "Compliant"
                compliant_count += 1
            else:
                status_val = "Error"
                error_count += 1

            detail = SCCMDeploymentAssetDetail(
                resource_id=res_id,
                server_ci_id=ci_id,
                hostname=hostname,
                status=status_val,
                status_type=(
                    "DeviceNotFound" if device is None
                    else "ActiveException" if has_active_exception
                    else "Success" if is_active
                    else "ClientInactive"
                ),
                error_code=(
                    "DEVICE_NOT_FOUND" if device is None
                    else "ACTIVE_EXCEPTION" if has_active_exception
                    else "0" if is_active
                    else "0x87D00324"
                ),
                status_time=now,
                source_payload={"blocked_by_active_exception": has_active_exception},
                reboot_pending=False,
            )
            asset_details_to_create.append(detail)

        run = SCCMDeploymentRun(
            run_id=run_id,
            change_number=data.get("change_number", ""),
            deployment_id=external_deployment_id,
            mode=data.get("mode", "STANDARD_PATCH"),
            target_collection_id=target_collection_id,
            assignment_id=assignment_id,
            window_start=data.get("window_start"),
            window_end=data.get("window_end"),
            reboot_policy=data.get("reboot_policy", "CLIENT_APPROVED"),
            status="completed",
            compliant_count=compliant_count,
            in_progress_count=0,
            error_count=error_count,
            unknown_count=unknown_count,
            skipped_count=skipped_count,
            started_at=now,
            completed_at=now,
            asset_details=asset_details_to_create,
            source_payload={"is_simulated": True},
        )

        try:
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception:
            self.db.rollback()
            raise

    def get_deployment_run(self, job_id: int | str) -> SCCMDeploymentRun | None:
        """Retrieve deployment run by database ID or external run_id."""
        if isinstance(job_id, int) or (isinstance(job_id, str) and job_id.isdigit()):
            return self.run_repo.get_by_id_with_details(int(job_id))
        return self.run_repo.get_by_run_id(str(job_id))

    def list_deployment_runs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List deployment run history."""
        self._validate_pagination(limit, offset)

        query = self.db.query(SCCMDeploymentRun)
        total = query.count()
        items = query.order_by(SCCMDeploymentRun.id.desc()).offset(offset).limit(limit).all()

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    # ------------------------------------------------------------------
    # Batch Synchronization / Import
    # ------------------------------------------------------------------

    def import_provider_data(self) -> dict[str, Any]:
        """Synchronize devices, collections, and deployments into PostgreSQL."""
        devices_imported = 0
        collections_imported = 0
        deployments_imported = 0
        errors = 0

        # 1. Devices
        if hasattr(self.provider, "list_devices"):
            try:
                raw_devices = self.provider.list_devices(limit=50000)
                for item in raw_devices:
                    res_id = str(
                        item.get("resource_id")
                        or item.get("source_device_id")
                        or item.get("ResourceID")
                        or item.get("id")
                        or ""
                    ).strip()
                    if not res_id:
                        continue
                    source_payload = item.get("source_payload") or item
                    ip_value = item.get("ip_address") or item.get("IPAddress") or item.get("IPAddresses")
                    if isinstance(ip_value, list):
                        ip_value = ",".join(str(value) for value in ip_value if value)
                    existing = self.device_repo.get_by_resource_id(res_id)
                    data = {
                        "resource_id": res_id,
                        "name": item.get("name") or item.get("hostname") or item.get("Name") or res_id,
                        "ip_address": ip_value,
                        "operating_system": item.get("operating_system") or item.get("OperatingSystemNameandVersion"),
                        "client_version": (
                            item.get("client_version")
                            or item.get("ClientVersion")
                            or source_payload.get("client_version")
                        ),
                        "client_active_status": item.get("client_active_status", item.get("ClientActiveStatus", False)),
                        "is_client": item.get("is_client", item.get("IsClient", False)),
                        "last_active_time": self._parse_datetime(
                            item.get("last_active_time") or item.get("LastActiveTime")
                        ),
                        "collection_id": item.get("collection_id") or item.get("CollectionID"),
                        "source_payload": source_payload,
                    }
                    if existing is None:
                        self.device_repo.create(data)
                    else:
                        self.device_repo.update(existing, data)
                    devices_imported += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        # 2. Collections
        if hasattr(self.provider, "list_collections"):
            try:
                raw_cols = self.provider.list_collections(limit=50000)
                for item in raw_cols:
                    col_id = str(
                        item.get("collection_id")
                        or item.get("CollectionID")
                        or item.get("id")
                        or ""
                    ).strip()
                    if not col_id:
                        continue
                    existing = self.collection_repo.get_by_collection_id(col_id)
                    data = {
                        "collection_id": col_id,
                        "name": item.get("name") or item.get("Name") or col_id,
                        "comment": item.get("comment") or item.get("Comment"),
                        "member_count": item.get("member_count", item.get("MemberCount", 0)),
                        "source_payload": item.get("source_payload") or item,
                    }
                    if existing is None:
                        self.collection_repo.create(data)
                    else:
                        self.collection_repo.update(existing, data)
                    collections_imported += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        # 3. Deployments
        if hasattr(self.provider, "list_deployments"):
            try:
                raw_deps = self.provider.list_deployments(limit=50000)
                for item in raw_deps:
                    assign_id = str(
                        item.get("assignment_id")
                        or item.get("AssignmentID")
                        or item.get("id")
                        or ""
                    ).strip()
                    if not assign_id:
                        continue
                    existing = self.deployment_repo.get_by_assignment_id(assign_id)
                    data = {
                        "assignment_id": assign_id,
                        "name": item.get("name") or item.get("AssignmentName") or item.get("Name") or assign_id,
                        "target_collection_id": (
                            item.get("target_collection_id")
                            or item.get("TargetCollectionID")
                            or item.get("CollectionID")
                            or item.get("collection_id")
                            or "DEFAULT"
                        ),
                        "reboot_policy": item.get("reboot_policy") or item.get("RebootPolicy"),
                        "status": item.get("status") or item.get("Status") or "Active",
                        "window_start": self._parse_datetime(
                            item.get("window_start") or item.get("WindowStart") or item.get("StartTime")
                        ),
                        "window_end": self._parse_datetime(
                            item.get("window_end") or item.get("WindowEnd") or item.get("Deadline")
                        ),
                        "source_payload": item.get("source_payload") or item,
                    }
                    if existing is None:
                        self.deployment_repo.create(data)
                    else:
                        self.deployment_repo.update(existing, data)
                    deployments_imported += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        return {
            "status": "completed",
            "devices_imported": devices_imported,
            "collections_imported": collections_imported,
            "deployments_imported": deployments_imported,
            "errors": errors,
        }
