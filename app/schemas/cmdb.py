"""Pydantic schemas for BMC Helix CMDB configuration items."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CMDBSchemaBase(BaseModel):
    """Shared validation configuration for CMDB schemas."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )


class CMDBServerBase(CMDBSchemaBase):
    """Common fields for server and operating-system CIs."""

    source_instance_id: str = Field(
        min_length=1,
        max_length=255,
    )

    ci_name: str | None = Field(
        default=None,
        max_length=255,
    )
    dns_host_name: str | None = Field(
        default=None,
        max_length=255,
    )
    ip_address: str | None = Field(
        default=None,
        max_length=45,
    )

    application_name: str | None = Field(
        default=None,
        max_length=255,
    )
    asset_owner: str | None = Field(
        default=None,
        max_length=255,
    )
    it_application_owner: str | None = Field(
        default=None,
        max_length=255,
    )

    system_environment: str | None = Field(
        default=None,
        max_length=100,
    )
    production_status: str | None = Field(
        default=None,
        max_length=50,
    )

    os_type: str | None = Field(
        default=None,
        max_length=100,
    )
    os_version: str | None = Field(
        default=None,
        max_length=255,
    )

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    is_virtual: str | None = Field(default=None, max_length=50)
    internet_facing: str | None = Field(default=None, max_length=50)
    virtual_system_type: str | None = Field(default=None, max_length=100)
    asset_type: str | None = Field(default=None, max_length=100)
    product_name: str | None = Field(default=None, max_length=255)
    server_type: str | None = Field(default=None, max_length=100)
    operating_system: str | None = Field(default=None, max_length=255)
    risk_classification: str | None = Field(default=None, max_length=50)
    target_date: str | None = Field(default=None, max_length=100)

    status: str | None = Field(
        default=None,
        max_length=50,
    )

    last_patch_updated_at: datetime | None = None

    source_payload: dict[str, Any] | None = Field(
        default=None,
    )


class CMDBServerCreate(CMDBServerBase):
    """Schema for creating a simulated server CI."""


class CMDBServerUpdate(CMDBSchemaBase):
    """Schema for updating selected fields on a server CI."""

    ci_name: str | None = Field(
        default=None,
        max_length=255,
    )
    dns_host_name: str | None = Field(
        default=None,
        max_length=255,
    )
    ip_address: str | None = Field(
        default=None,
        max_length=45,
    )

    application_name: str | None = Field(
        default=None,
        max_length=255,
    )
    asset_owner: str | None = Field(
        default=None,
        max_length=255,
    )
    it_application_owner: str | None = Field(
        default=None,
        max_length=255,
    )

    system_environment: str | None = Field(
        default=None,
        max_length=100,
    )
    production_status: str | None = Field(
        default=None,
        max_length=50,
    )

    os_type: str | None = Field(
        default=None,
        max_length=100,
    )
    os_version: str | None = Field(
        default=None,
        max_length=255,
    )

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    is_virtual: str | None = Field(default=None, max_length=50)
    internet_facing: str | None = Field(default=None, max_length=50)
    virtual_system_type: str | None = Field(default=None, max_length=100)
    asset_type: str | None = Field(default=None, max_length=100)
    product_name: str | None = Field(default=None, max_length=255)
    server_type: str | None = Field(default=None, max_length=100)
    operating_system: str | None = Field(default=None, max_length=255)
    risk_classification: str | None = Field(default=None, max_length=50)
    target_date: str | None = Field(default=None, max_length=100)

    status: str | None = Field(
        default=None,
        max_length=50,
    )

    last_patch_updated_at: datetime | None = None

    source_payload: dict[str, Any] | None = None


class CMDBServerResponse(CMDBServerBase):
    """Schema returned for a server CI."""

    id: int
    created_at: datetime
    updated_at: datetime


class CMDBServerListResponse(BaseModel):
    """Paginated list of CMDB servers."""

    model_config = ConfigDict(extra="forbid")

    items: list[CMDBServerResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class CMDBMiddlewareBase(CMDBSchemaBase):
    """Base fields for middleware configuration items."""

    source_instance_id: str = Field(min_length=1, max_length=255)
    ci_name: str | None = Field(default=None, max_length=255)
    server_instance_id: str | None = Field(default=None, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    location: str | None = Field(default=None, max_length=255)
    application_name: str | None = Field(default=None, max_length=255)
    asset_owner: str | None = Field(default=None, max_length=255)
    it_application_owner: str | None = Field(default=None, max_length=255)
    middleware_type: str | None = Field(default=None, max_length=100)
    version: str | None = Field(default=None, max_length=100)
    recommended_version: str | None = Field(default=None, max_length=100)
    environment: str | None = Field(default=None, max_length=100)
    production_status: str | None = Field(default=None, max_length=50)
    core_count: int | None = None
    os_type: str | None = Field(default=None, max_length=100)
    latest_patch_release_date: str | None = Field(default=None, max_length=100)
    end_of_support_date: str | None = Field(default=None, max_length=100)
    target_date: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=50)
    source_payload: dict[str, Any] | None = None


class CMDBMiddlewareCreate(CMDBMiddlewareBase):
    """Schema for creating a middleware CI."""


class CMDBMiddlewareUpdate(CMDBSchemaBase):
    """Schema for updating a middleware CI."""

    ci_name: str | None = None
    server_instance_id: str | None = None
    hostname: str | None = None
    ip_address: str | None = None
    location: str | None = None
    application_name: str | None = None
    asset_owner: str | None = None
    it_application_owner: str | None = None
    middleware_type: str | None = None
    version: str | None = None
    recommended_version: str | None = None
    environment: str | None = None
    production_status: str | None = None
    core_count: int | None = None
    os_type: str | None = None
    status: str | None = None
    source_payload: dict[str, Any] | None = None


class CMDBMiddlewareResponse(CMDBMiddlewareBase):
    """Schema returned for a middleware CI."""

    id: int
    created_at: datetime
    updated_at: datetime


class CMDBMiddlewareListResponse(BaseModel):
    """Paginated list of CMDB middleware."""

    model_config = ConfigDict(extra="forbid")

    items: list[CMDBMiddlewareResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class CMDBDatabaseBase(CMDBSchemaBase):
    """Base fields for database configuration items."""

    source_instance_id: str = Field(min_length=1, max_length=255)
    ci_name: str | None = Field(default=None, max_length=255)
    server_instance_id: str | None = Field(default=None, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    location: str | None = Field(default=None, max_length=255)
    asset_owner: str | None = Field(default=None, max_length=255)
    database_type: str | None = Field(default=None, max_length=100)
    version: str | None = Field(default=None, max_length=100)
    environment: str | None = Field(default=None, max_length=100)
    production_status: str | None = Field(default=None, max_length=50)
    risk_classification: str | None = Field(default=None, max_length=50)
    last_patch_updated_at: datetime | None = None
    target_date: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=50)
    source_payload: dict[str, Any] | None = None


class CMDBDatabaseCreate(CMDBDatabaseBase):
    """Schema for creating a database CI."""


class CMDBDatabaseUpdate(CMDBSchemaBase):
    """Schema for updating a database CI."""

    ci_name: str | None = None
    server_instance_id: str | None = None
    hostname: str | None = None
    ip_address: str | None = None
    location: str | None = None
    asset_owner: str | None = None
    database_type: str | None = None
    version: str | None = None
    environment: str | None = None
    production_status: str | None = None
    risk_classification: str | None = None
    last_patch_updated_at: datetime | None = None
    status: str | None = None
    source_payload: dict[str, Any] | None = None


class CMDBDatabaseResponse(CMDBDatabaseBase):
    """Schema returned for a database CI."""

    id: int
    created_at: datetime
    updated_at: datetime


class CMDBDatabaseListResponse(BaseModel):
    """Paginated list of CMDB databases."""

    model_config = ConfigDict(extra="forbid")

    items: list[CMDBDatabaseResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class CMDBRelationshipBase(CMDBSchemaBase):
    """Base fields for CMDB CI relationships."""

    source_relationship_id: str = Field(min_length=1, max_length=255)
    source_instance_id: str = Field(min_length=1, max_length=255)
    destination_instance_id: str = Field(min_length=1, max_length=255)
    relationship_type: str = Field(min_length=1, max_length=255)
    source_payload: dict[str, Any] | None = None


class CMDBRelationshipCreate(CMDBRelationshipBase):
    """Schema for creating a CMDB CI relationship."""


class CMDBRelationshipResponse(CMDBRelationshipBase):
    """Schema returned for a relationship between CMDB CIs."""

    id: int
    created_at: datetime


class CMDBRelationshipListResponse(BaseModel):
    """Paginated list of CMDB relationships."""

    model_config = ConfigDict(extra="forbid")

    items: list[CMDBRelationshipResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class CMDBLookupResponse(BaseModel):
    """Correlation outcome for IP-to-server resolution according to BRD."""

    model_config = ConfigDict(extra="forbid")

    ip_address: str
    correlation_outcome: str  # MATCHED, CMDB_NOT_FOUND, AMBIGUOUS_MATCH, CMDB_CI_INACTIVE
    matched_servers: list[CMDBServerResponse]
    message: str


class CMDBImportResponse(BaseModel):
    """Summary of CMDB provider import operation."""

    model_config = ConfigDict(extra="forbid")

    servers_imported: int
    middleware_imported: int
    databases_imported: int
    errors: int