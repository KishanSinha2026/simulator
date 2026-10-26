"""FastAPI endpoints for Tenable vulnerability findings and scans.

Implements unified BRD Section 4.1 routes:
- GET /findings (vulnerability details with CVSS v3/v4 score precedence)
- GET /findings/{finding_id}
- GET /scans (scanner execution and job details)
- POST /import (synchronize/import findings and scans into PostgreSQL)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.tenable import (
    TenableFindingListResponse,
    TenableFindingResponse,
    TenableImportResponse,
    TenableScanListResponse,
)
from app.services.tenable_service import TenableService


router = APIRouter(
    prefix="/tenable",
    tags=["Tenable"],
)


def get_tenable_service(
    db: Session = Depends(get_db),
) -> TenableService:
    """Build the Tenable service for the current request."""
    return TenableService(db)


@router.get(
    "/findings",
    response_model=TenableFindingListResponse,
    summary="List vulnerability findings",
)
def list_findings(
    limit: int = Query(default=100, ge=1, le=50000, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    severity: str | None = Query(default=None, min_length=1, description="Filter by severity (Critical, High, Medium, Low)"),
    ip_address: str | None = Query(
        default=None,
        min_length=1,
        max_length=45,
        description="Filter findings by host IP address",
    ),
    include_informational: bool = Query(
        default=False,
        description="Include informational/non-actionable findings (excluded by default per BRD)",
    ),
    service: TenableService = Depends(get_tenable_service),
):
    """Retrieve normalized Tenable findings. Automatically serves live API data if configured, or local/JSON data."""
    try:
        return service.list_findings(
            limit=limit,
            offset=offset,
            severity=severity,
            ip_address=ip_address,
            include_informational=include_informational,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/findings/{finding_id}",
    response_model=TenableFindingResponse,
    summary="Get finding details by ID",
)
def get_finding(
    finding_id: int,
    service: TenableService = Depends(get_tenable_service),
):
    """Retrieve complete vulnerability finding details including 54 normalized fields and CVEs."""
    if finding_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="finding_id must be greater than zero",
        )

    finding = service.get_finding(finding_id)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenable finding not found",
        )
    return finding


@router.get(
    "/scans",
    response_model=TenableScanListResponse,
    summary="List scanner executions",
)
def list_scans(
    limit: int = Query(default=100, ge=1, le=50000, description="Max scans to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    service: TenableService = Depends(get_tenable_service),
):
    """List Tenable scan jobs and metadata."""
    try:
        return service.list_scans(limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/import",
    response_model=TenableImportResponse,
    summary="Import and synchronize findings into PostgreSQL",
)
def import_findings(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    service: TenableService = Depends(get_tenable_service),
) -> dict[str, Any]:
    """Synchronize findings and scans from the active source (remote API or JSON fixtures) into PostgreSQL."""
    try:
        return service.import_provider_findings(
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to import Tenable data.",
        ) from None