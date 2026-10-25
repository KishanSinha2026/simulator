"""FastAPI endpoints for BMC Helix ITSM change requests."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.itsm import (
    ITSMChangeCreate,
    ITSMChangeResponse,
    ITSMChangeUpdate,
)
from app.services.itsm_service import ITSMService

router = APIRouter(prefix="/itsm", tags=["BMC Helix ITSM"])


def get_itsm_service(
    db: Session = Depends(get_db),
) -> ITSMService:
    """Create the ITSM service for the current request."""
    return ITSMService(db)


@router.get("/changes", response_model=PaginatedResponse)
def list_changes(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    service: ITSMService = Depends(get_itsm_service),
):
    """List change requests stored in PostgreSQL."""
    return service.list_changes(
        limit=limit,
        offset=offset,
        status=status_filter,
    )


@router.get(
    "/changes/{change_id}",
    response_model=ITSMChangeResponse,
)
def get_change(
    change_id: int,
    service: ITSMService = Depends(get_itsm_service),
):
    """Retrieve a change request by database ID."""
    change = service.get_change(change_id)

    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ITSM change not found",
        )

    return change


@router.post(
    "/changes",
    response_model=ITSMChangeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_change(
    payload: ITSMChangeCreate,
    service: ITSMService = Depends(get_itsm_service),
):
    """Create a simulated change request in PostgreSQL."""
    try:
        return service.create_change(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create ITSM change",
        ) from None


@router.patch(
    "/changes/{change_id}",
    response_model=ITSMChangeResponse,
)
def update_change(
    change_id: int,
    payload: ITSMChangeUpdate,
    service: ITSMService = Depends(get_itsm_service),
):
    """Update selected fields of a stored change request."""
    try:
        change = service.update_change(change_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update ITSM change",
        ) from None

    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ITSM change not found",
        )

    return change