"""Pydantic schemas for SCCM 2509 Windows execution and deployment tracking."""

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, model_validator


class SCCMDeviceResponse(BaseModel):
    """Configuration Manager managed device representation."""

    id: int
    resource_id: str
    name: str
    ip_address: str | None = None
    operating_system: str | None = None
    client_version: str | None = None
    client_active_status: bool
    is_client: bool
    last_active_time: datetime | None = None
    collection_id: str | None = None
    source_payload: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def source_device_id(self) -> str:
        """BRD name for SCCM ResourceID, retaining the legacy field too."""
        return self.resource_id

    @computed_field
    @property
    def hostname(self) -> str:
        """BRD name for the SCCM device name, retaining the legacy field too."""
        return self.name


class SCCMDeviceListResponse(BaseModel):
    """Paginated list of Configuration Manager devices."""

    items: list[SCCMDeviceResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class SCCMCollectionResponse(BaseModel):
    """Configuration Manager device collection."""

    id: int
    collection_id: str
    name: str
    comment: str | None = None
    member_count: int
    source_payload: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SCCMCollectionListResponse(BaseModel):
    """Paginated list of Configuration Manager collections."""

    items: list[SCCMCollectionResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class SCCMDeploymentResponse(BaseModel):
    """Configuration Manager software update group deployment policy."""

    id: int
    assignment_id: str
    name: str
    target_collection_id: str
    reboot_policy: str | None = None
    status: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    source_payload: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SCCMDeploymentListResponse(BaseModel):
    """Paginated list of SCCM deployment policies."""

    items: list[SCCMDeploymentResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class SCCMTargetItem(BaseModel):
    """Target host entry matching BRD Section 8.5.5."""

    model_config = ConfigDict(populate_by_name=True)

    server_ci_id: str | None = Field(default=None, description="Authoritative CMDB instance ID")
    resource_id: str = Field(
        ..., min_length=1,
        validation_alias=AliasChoices("resource_id", "source_device_id"),
        description="SCCM ResourceID / BRD source_device_id",
    )
    hostname: str = Field(
        ..., min_length=1,
        validation_alias=AliasChoices("hostname", "name"),
        description="Target host FQDN",
    )


class SCCMMaintenanceWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime | None = None
    end: datetime | None = None


class SCCMJobLaunchRequest(BaseModel):
    """SCCM guarded patch execution launch contract matching BRD Section 8.5.5."""

    model_config = ConfigDict(extra="ignore")

    run_id: str | None = Field(default=None, min_length=1, max_length=100, description="Optional caller run identifier")
    deployment_id: str | None = Field(default=None, min_length=1, max_length=100, description="BRD SCCM deployment identifier")
    change_number: str | None = Field(default=None, max_length=100, description="Related Helix change request ID")
    mode: str = Field(default="STANDARD_PATCH", max_length=100, description="Approved SCCM execution mode")
    targets: list[SCCMTargetItem] = Field(..., min_length=1, description="Target host set to patch")
    target_collection_id: str | None = Field(default=None, max_length=100, description="Approved target CollectionID")
    assignment_id: str | None = Field(default=None, max_length=100, description="Approved update group AssignmentID")
    maintenance_window: SCCMMaintenanceWindow | None = None
    window_start: datetime | None = Field(default=None, description="Approved maintenance window start")
    window_end: datetime | None = Field(default=None, description="Approved maintenance window end")
    reboot_policy: str = Field(default="CLIENT_APPROVED", max_length=100, description="Reboot control policy")

    @model_validator(mode="after")
    def normalize_window_and_policy(self) -> "SCCMJobLaunchRequest":
        if self.maintenance_window is not None:
            self.window_start = self.window_start or self.maintenance_window.start
            self.window_end = self.window_end or self.maintenance_window.end
        if not self.deployment_id and not self.assignment_id:
            raise ValueError("deployment_id or assignment_id is required")
        if self.window_start and self.window_end and self.window_start >= self.window_end:
            raise ValueError("maintenance window start must be before end")
        return self


class SCCMDeploymentAssetDetailResponse(BaseModel):
    """Per-device status and compliance outcome."""

    id: int
    resource_id: str
    server_ci_id: str | None = None
    hostname: str
    status: str = Field(description="Compliant, In Progress, Error, Unknown, Skipped")
    status_type: str | None = None
    error_code: str | None = None
    status_time: datetime | None = None
    reboot_pending: bool = False

    model_config = ConfigDict(from_attributes=True)


class SCCMDeploymentRunResponse(BaseModel):
    """SCCM deployment run execution details and compliance breakdown."""

    id: int
    run_id: str
    deployment_id: str | None = None
    change_number: str
    mode: str
    target_collection_id: str
    assignment_id: str
    window_start: datetime | None = None
    window_end: datetime | None = None
    reboot_policy: str
    status: str
    compliant_count: int
    in_progress_count: int
    error_count: int
    unknown_count: int
    skipped_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    asset_details: list[SCCMDeploymentAssetDetailResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def source_job_id(self) -> str:
        """Expose the BRD source_job_id while retaining run_id for compatibility."""
        return self.run_id

    @computed_field
    @property
    def total_targets(self) -> int:
        return len(self.asset_details)


class SCCMDeploymentRunListResponse(BaseModel):
    """Paginated list of SCCM deployment runs."""

    items: list[SCCMDeploymentRunResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class SCCMImportResponse(BaseModel):
    """Synchronization outcome for SCCM data import."""

    status: str = Field(default="completed")
    devices_imported: int = Field(ge=0)
    collections_imported: int = Field(ge=0)
    deployments_imported: int = Field(ge=0)
    errors: int = Field(ge=0)
