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


class CMDBMiddlewareResponse(CMDBSchemaBase):
    """Schema returned for a middleware CI."""

    id: int
    source_instance_id: str

    ci_name: str | None = None
    server_instance_id: str | None = None

    middleware_type: str | None = None
    version: str | None = None
    status: str | None = None

    source_payload: dict[str, Any] | None = None

    created_at: datetime
    updated_at: datetime


class CMDBDatabaseResponse(CMDBSchemaBase):
    """Schema returned for a database CI."""

    id: int
    source_instance_id: str

    ci_name: str | None = None
    server_instance_id: str | None = None

    database_type: str | None = None
    version: str | None = None
    status: str | None = None

    source_payload: dict[str, Any] | None = None

    created_at: datetime
    updated_at: datetime


class CMDBRelationshipResponse(CMDBSchemaBase):
    """Schema returned for a relationship between CMDB CIs."""

    id: int
    source_relationship_id: str
    source_instance_id: str
    destination_instance_id: str
    relationship_type: str

    source_payload: dict[str, Any] | None = None
    created_at: datetime