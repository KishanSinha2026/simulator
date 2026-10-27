"""Pydantic schemas for Squad1 vulnerability lifecycle tracking."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Squad1VulnerabilityBase(BaseModel):
    """Base fields for Squad1 vulnerability records."""

    model_config = ConfigDict(extra="ignore")

    vulnerability_no: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Core Squad1 vulnerability identifier",
    )
    plugin_id: int | None = Field(
        default=None,
        description="Associated security scanner plugin ID",
    )
    target: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Target host IP or FQDN",
    )
    vulnerability_name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Title/name of vulnerability",
    )
    description: str | None = Field(default=None, description="Detailed vulnerability description")
    protocol: str | None = Field(default=None, max_length=50, description="Transport protocol (e.g. tcp)")
    port: int | None = Field(default=None, ge=0, le=65535, description="Network port")
    risk_rating: str | None = Field(default=None, max_length=50, description="Risk rating (Critical, High, Medium, Low)")
    status: str | None = Field(default="Open", max_length=50, description="Status (Open, In Progress, Exception, Closed)")
    recommendation: str | None = Field(default=None, description="Remediation recommendation")
    solution_category: str | None = Field(default=None, max_length=100, description="Solution category")
    plugin_output: str | None = Field(default=None, description="POC / Plugin output evidence")
    owasp_mapping: str | None = Field(default=None, max_length=100, description="OWASP category mapping")
    cve_id: str | None = Field(default=None, max_length=100, description="Primary CVE identifier")
    cvss_score: float | None = Field(default=None, ge=0.0, le=10.0, description="CVSS base score")
    risk_type: str | None = Field(default=None, max_length=100, description="Risk classification")
    vulnerability_holder: str | None = Field(default=None, max_length=255, description="Responsible owner")
    vulnerability_holder_department: str | None = Field(default=None, max_length=255, description="Owner department")
    vulnerability_holder_location: str | None = Field(default=None, max_length=255, description="Owner location")
    bu_head: str | None = Field(default=None, max_length=255, description="Business unit head")
    report_published_date: datetime | None = Field(default=None, description="Publish date")
    planned_remediation_date: datetime | None = Field(default=None, description="Target remediation date")
    ageing: int | None = Field(default=None, ge=0, description="Age in days")
    risk_severity_change_date: datetime | None = Field(default=None, description="Severity modification date")
    exception_id: str | None = Field(default=None, max_length=100, description="Squad1 approved exception ID")
    exception_end_date: datetime | None = Field(default=None, description="Exception expiry timestamp")
    exception_status: str | None = Field(default=None, max_length=50, description="Exception approval state")
    source_payload: dict[str, Any] | None = Field(default=None, description="Raw source fields")


class Squad1VulnerabilityCreate(Squad1VulnerabilityBase):
    """Payload for creating or idempotently updating a Squad1 vulnerability."""
    pass


class Squad1VulnerabilityResponse(Squad1VulnerabilityBase):
    """Squad1 vulnerability record returned by API."""

    id: int = Field(..., description="Internal database ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class Squad1VulnerabilityListResponse(BaseModel):
    """Paginated list of Squad1 vulnerability records."""

    items: list[Squad1VulnerabilityResponse]
    total: int = Field(ge=0, description="Total matching records")
    limit: int = Field(ge=1, le=50000, description="Page limit")
    offset: int = Field(ge=0, description="Page offset")
    has_more: bool = Field(description="Whether more records exist")


class Squad1ExceptionResponse(BaseModel):
    """Squad1 approved exception record per BRD Section 4.2."""

    id: int
    vulnerability_no: str
    target: str
    vulnerability_name: str
    exception_id: str
    exception_end_date: datetime | None
    exception_status: str | None
    status: str | None

    model_config = ConfigDict(from_attributes=True)


class Squad1ExceptionListResponse(BaseModel):
    """Paginated list of Squad1 active exceptions."""

    items: list[Squad1ExceptionResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class Squad1ImportResponse(BaseModel):
    """Synchronization outcome for Squad1 data import."""

    status: str = Field(default="completed")
    records_received: int = Field(ge=0)
    records_created: int = Field(ge=0)
    records_updated: int = Field(ge=0)
    exceptions_count: int = Field(ge=0)
    errors: int = Field(ge=0)
