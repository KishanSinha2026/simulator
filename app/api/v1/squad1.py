"""FastAPI endpoints for Squad1 vulnerability lifecycle and exception management.

Implements unified BRD Section 4.2 routes:
- GET /vulnerabilities (list findings/vulnerabilities with optional status/target filters)
- POST /vulnerabilities (create or idempotently update finding)
- GET /vulnerabilities/{vulnerability_id} (read vulnerability details)
- GET /exceptions (read active exceptions with Exception_ID and Exception_END_Date)
- POST /import (synchronize/import Squad1 findings into PostgreSQL)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.squad1 import (
    Squad1ExceptionListResponse,
    Squad1ImportResponse,
    Squad1VulnerabilityCreate,
    Squad1VulnerabilityListResponse,
    Squad1VulnerabilityResponse,
)
from app.services.squad1_service import Squad1Service


router = APIRouter(
    prefix="/squad1",
    tags=["Squad1"],
)


def get_squad1_service(
    db: Session = Depends(get_db),
) -> Squad1Service:
    """Create Squad1 service for the current request."""
    return Squad1Service(db)


@router.get(
    "/vulnerabilities",
    response_model=Squad1VulnerabilityListResponse,
    summary="List Squad1 vulnerabilities",
)
def list_vulnerabilities(
    limit: int = Query(default=100, ge=1, le=50000, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status (Open, Closed, Exception)"),
    target: str | None = Query(default=None, description="Filter by target IP or hostname"),
    risk_rating: str | None = Query(default=None, description="Filter by risk rating (Critical, High, Medium, Low)"),
    service: Squad1Service = Depends(get_squad1_service),
) -> dict[str, Any]:
    """Retrieve Squad1 vulnerability findings. Serves live API data if configured, or local/JSON data."""
    try:
        return service.list_vulnerabilities(
            limit=limit,
            offset=offset,
            status=status_filter,
            target=target,
            risk_rating=risk_rating,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/findings",
    response_model=Squad1VulnerabilityListResponse,
    summary="List Squad1 findings (alias for /vulnerabilities)",
)
def list_findings_alias(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    target: str | None = Query(default=None),
    risk_rating: str | None = Query(default=None),
    service: Squad1Service = Depends(get_squad1_service),
) -> dict[str, Any]:
    """Alias for listing Squad1 findings."""
    return list_vulnerabilities(
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        target=target,
        risk_rating=risk_rating,
        service=service,
    )


@router.post(
    "/vulnerabilities",
    response_model=Squad1VulnerabilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update Squad1 vulnerability",
)
def create_vulnerability(
    payload: Squad1VulnerabilityCreate,
    service: Squad1Service = Depends(get_squad1_service),
):
    """Idempotently create or update a Squad1 vulnerability record."""
    try:
        return service.create_vulnerability(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/vulnerabilities/{vulnerability_id}",
    response_model=Squad1VulnerabilityResponse,
    summary="Get Squad1 vulnerability details by ID",
)
def get_vulnerability(
    vulnerability_id: int,
    service: Squad1Service = Depends(get_squad1_service),
):
    """Retrieve complete Squad1 vulnerability record."""
    if vulnerability_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="vulnerability_id must be greater than zero",
        )
    record = service.get_vulnerability(vulnerability_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Squad1 vulnerability not found",
        )
    return record


@router.get(
    "/exceptions",
    response_model=Squad1ExceptionListResponse,
    summary="List active Squad1 exceptions (BRD Section 4.2)",
)
def list_exceptions(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    service: Squad1Service = Depends(get_squad1_service),
) -> dict[str, Any]:
    """Retrieve approved Squad1 exceptions, including Exception_ID and Exception_END_Date."""
    try:
        return service.list_exceptions(limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/import",
    response_model=Squad1ImportResponse,
    summary="Import and synchronize Squad1 vulnerabilities into PostgreSQL",
)
def import_squad1_data(
    limit: int = Query(default=50000, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    service: Squad1Service = Depends(get_squad1_service),
) -> dict[str, Any]:
    """Synchronize Squad1 vulnerability findings into PostgreSQL."""
    return service.import_provider_data(limit=limit, offset=offset)
