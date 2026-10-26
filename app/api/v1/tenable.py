"""FastAPI endpoints for Tenable vulnerability findings and ingestion."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.tenable import (
    TenableFindingCreate,
    TenableFindingResponse,
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
    response_model=PaginatedResponse,
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
    actionable_only: bool = Query(
        default=False,
        description=(
            "Exclude informational findings from the returned results."
        ),
    ),
    service: TenableService = Depends(get_tenable_service),
) -> dict[str, Any]:
    """List findings persisted in PostgreSQL."""
    try:
        return service.list_findings(
            limit=limit,
            offset=offset,
            severity=severity,
            ip_address=ip_address,
            actionable_only=actionable_only,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/provider/findings",
)
def list_provider_findings(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    severity: str | None = Query(default=None, min_length=1),
    date_range: int | None = Query(default=None, ge=1),
    service: TenableService = Depends(get_tenable_service),
) -> list[dict[str, Any]]:
    """Preview findings from the configured Tenable provider.

    This endpoint does not persist the returned records.
    """
    filters: dict[str, Any] = {}

    if severity is not None:
        filters["severity"] = severity

    if date_range is not None:
        filters["date_range"] = date_range

    try:
        return service.list_provider_findings(
            limit=limit,
            offset=offset,
            filters=filters or None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to retrieve findings from the Tenable provider.",
        ) from None


@router.post(
    "/findings/import",
    status_code=status.HTTP_200_OK,
)
def import_provider_findings(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    severity: str | None = Query(default=None, min_length=1),
    date_range: int | None = Query(default=None, ge=1),
    service: TenableService = Depends(get_tenable_service),
) -> dict[str, Any]:
    """Import findings from Tenable into PostgreSQL.

    The service handles source normalization, stable-ID matching,
    CVE persistence, informational-finding tracking, and transactions.

    Records missing a reliable source finding identifier are skipped
    rather than assigned a fabricated identity.
    """
    filters: dict[str, Any] = {}

    if severity is not None:
        filters["severity"] = severity

    if date_range is not None:
        filters["date_range"] = date_range

    try:
        return service.import_provider_findings(
            limit=limit,
            offset=offset,
            filters=filters or None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The import conflicts with an existing database record.",
        ) from None
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Tenable import failed while communicating with the provider.",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to import Tenable findings.",
        ) from None


@router.get(
    "/findings/{finding_id}",
    response_model=TenableFindingResponse,
)
def get_finding(
    finding_id: int,
    service: TenableService = Depends(get_tenable_service),
) -> Any:
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
) -> Any:
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
                "or violates a database constraint."
            ),
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create Tenable finding.",
        ) from None