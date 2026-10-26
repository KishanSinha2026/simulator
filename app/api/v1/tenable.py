"""FastAPI endpoints for Tenable vulnerability findings."""

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
    service: TenableService = Depends(get_tenable_service),
):
    """List findings persisted in PostgreSQL."""
    return service.list_findings(
        limit=limit,
        offset=offset,
        severity=severity,
        ip_address=ip_address,
    )


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
        # Do not expose database details or secrets in API responses.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create Tenable finding",
        ) from None