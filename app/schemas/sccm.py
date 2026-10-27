"""Pydantic schemas for SCCM 2509 Windows execution and deployment tracking."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SCCMDeviceResponse(BaseModel):
    """Configuration Manager managed device representation."""

    id: int
    resource_id: str
    name: str
    ip_address: str | None = None
    operating_system: str | None = None
    client_active_status: bool
    is_client: bool
    last_active_time: datetime | None = None
    collection_id: str | None = None
    source_payload: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    server_ci_id: str | None = Field(default=None, description="Authoritative CMDB instance ID")
    resource_id: str = Field(..., min_length=1, description="SCCM ResourceID")
    hostname: str = Field(..., min_length=1, description="Target host FQDN")


class SCCMJobLaunchRequest(BaseModel):
    """SCCM guarded patch execution launch contract matching BRD Section 8.5.5."""

    model_config = ConfigDict(extra="ignore")

    run_id: str = Field(..., min_length=1, max_length=100, description="External run identifier (e.g. RUN-WIN-001)")
    change_number: str = Field(..., min_length=1, max_length=100, description="Approved Helix change request ID")
    mode: str = Field(default="STANDARD_PATCH", max_length=100, description="Approved SCCM execution mode")
    targets: list[SCCMTargetItem] = Field(..., min_length=1, description="Target host set to patch")
    target_collection_id: str = Field(..., min_length=1, max_length=100, description="Approved target CollectionID")
    assignment_id: str = Field(..., min_length=1, max_length=100, description="Approved update group AssignmentID")
    window_start: datetime | None = Field(default=None, description="Approved maintenance window start")
    window_end: datetime | None = Field(default=None, description="Approved maintenance window end")
    reboot_policy: str = Field(default="CLIENT_APPROVED", max_length=100, description="Reboot control policy")


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

    model_config = ConfigDict(from_attributes=True)


class SCCMDeploymentRunResponse(BaseModel):
    """SCCM deployment run execution details and compliance breakdown."""

    id: int
    run_id: str
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
