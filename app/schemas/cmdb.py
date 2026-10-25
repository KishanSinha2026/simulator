"""Pydantic schemas for CMDB configuration items."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CMDBServerBase(BaseModel):
    """Common server configuration item fields."""

    source_id: str | None = Field(default=None, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    operating_system: str | None = Field(default=None, max_length=255)
    os_version: str | None = Field(default=None, max_length=255)
    environment: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    serial_number: str | None = Field(default=None, max_length=255)
    last_patch_updated: datetime | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class CMDBServerCreate(CMDBServerBase):
    """Schema for creating a simulated server CI."""


class CMDBServerUpdate(BaseModel):
    """Schema for updating selected server CI fields."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    operating_system: str | None = Field(default=None, max_length=255)
    os_version: str | None = Field(default=None, max_length=255)
    environment: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=100)
    last_patch_updated: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class CMDBServerResponse(CMDBServerBase):
    """Schema returned for a server CI."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CMDBMiddlewareResponse(BaseModel):
    """Middleware CI response."""

    id: int
    source_id: str | None = None
    name: str
    server_id: str | None = None
    product_name: str | None = None
    product_version: str | None = None
    status: str | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CMDBDatabaseResponse(BaseModel):
    """Database CI response."""

    id: int
    source_id: str | None = None
    name: str
    server_id: str | None = None
    database_type: str | None = None
    database_version: str | None = None
    status: str | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, extra="forbid")