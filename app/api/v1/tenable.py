"""FastAPI endpoints for Tenable vulnerability findings and scans."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.tenable import (
    TenableFindingCreate,
    TenableFindingListResponse,
    TenableFindingResponse,
    TenableImportResponse,
    TenableScanCreate,
    TenableScanListResponse,
    TenableScanResponse,
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


# ======================================================================
# Database Routes (Findings)
# ======================================================================


@router.get(
    "/findings",
    response_model=TenableFindingListResponse,
)
def list_findings(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    severity: str | None = Query(default=None, min_length=1),
    ip_address: str | None = Query(
        default=None,
        min_length=1,
        max_length=45,
    ),
    include_informational: bool = Query(default=False),
    service: TenableService = Depends(get_tenable_service),
):
    """List persisted findings from PostgreSQL; informational records are excluded by default."""
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
)
def get_finding(
    finding_id: int,
    service: TenableService = Depends(get_tenable_service),
):
    """Retrieve a persisted finding by its database ID."""
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


@router.post(
    "/findings",
    response_model=TenableFindingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_finding(
    payload: TenableFindingCreate,
    service: TenableService = Depends(get_tenable_service),
):
    """Create a simulated Tenable finding in PostgreSQL."""
    try:
        return service.create_finding(payload)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The finding conflicts with an existing record "
                "or violates a database constraint"
            ),
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create Tenable finding.",
        ) from None


# ======================================================================
# Database Routes (Scans)
# ======================================================================


@router.get(
    "/scans",
    response_model=TenableScanListResponse,
)
def list_scans(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: TenableService = Depends(get_tenable_service),
):
    """List persisted scans from PostgreSQL."""
    try:
        return service.list_scans(limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/scans/{scan_id}",
    response_model=TenableScanResponse,
)
def get_scan(
    scan_id: int,
    service: TenableService = Depends(get_tenable_service),
):
    """Retrieve a persisted scan by database ID."""
    if scan_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scan_id must be greater than zero",
        )

    scan = service.get_scan(scan_id)
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenable scan not found",
        )
    return scan


@router.post(
    "/scans",
    response_model=TenableScanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_scan(
    payload: TenableScanCreate,
    service: TenableService = Depends(get_tenable_service),
):
    """Create a simulated Tenable scan in PostgreSQL."""
    try:
        return service.create_scan(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scan conflicts with existing record or violates constraint",
        ) from None


# ======================================================================
# Data Import & Synchronization Route
# ======================================================================


@router.post(
    "/import",
    response_model=TenableImportResponse,
)
def import_findings(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: TenableService = Depends(get_tenable_service),
) -> dict[str, Any]:
    """Import and normalize findings and scans from the active provider into PostgreSQL."""
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


# ======================================================================
# Provider / JSON Aliases (Hidden from Swagger UI to prevent duplicates)
# ======================================================================


@router.get(
    "/provider/findings",
    include_in_schema=False,
)
def list_provider_findings(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    severity: str | None = Query(default=None, min_length=1),
    actionable_only: bool = Query(default=False),
    service: TenableService = Depends(get_tenable_service),
) -> list[dict[str, Any]]:
    """Preview findings directly from the configured provider."""
    filter_dict: dict[str, Any] = {}
    if severity:
        filter_dict["severity"] = severity
    records = service.list_provider_findings(
        limit=limit,
        offset=offset,
        filters=filter_dict or None,
    )
    if actionable_only:
        records = [
            r for r in records
            if r.get("source_payload", {}).get("_brd_normalization", {}).get("actionable") is not False
        ]
    return records


@router.get(
    "/provider/scans",
    include_in_schema=False,
)
def list_provider_scans(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: TenableService = Depends(get_tenable_service),
) -> list[dict[str, Any]]:
    """Preview scans directly from the configured provider."""
    return service.list_provider_scans(limit=limit, offset=offset)


@router.post(
    "/provider/findings",
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_provider_finding(
    payload: dict[str, Any],
    service: TenableService = Depends(get_tenable_service),
) -> dict[str, Any]:
    """Create a simulated finding directly in the active JSON provider."""
    return service.create_provider_finding(payload)


@router.post(
    "/provider/import",
    response_model=TenableImportResponse,
    include_in_schema=False,
)
def import_provider_findings_alias(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: TenableService = Depends(get_tenable_service),
) -> dict[str, Any]:
    """Alias for /import preserving backwards compatibility."""
    return service.import_provider_findings(limit=limit, offset=offset)