"""FastAPI endpoints for BMC Helix ITSM (and ISTM alias) change requests and worklogs.

Implements unified BRD Section 4.4 routes:
- GET /changes (list change requests with optional status filtering)
- POST /changes (create change request with 19 BRD Appendix D QA fields)
- GET /changes/{change_id} (read change request details)
- GET /changes/{change_id}/worklogs (list worklogs for change request)
- POST /changes/{change_id}/worklogs (add worklog to change request)
- POST /import (synchronize/import changes and worklogs into PostgreSQL)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.itsm import (
    ITSMChangeCreate,
    ITSMChangeListResponse,
    ITSMChangeResponse,
    ITSMChangeUpdate,
    ITSMImportResponse,
    ITSMWorklogCreate,
    ITSMWorklogListResponse,
    ITSMWorklogResponse,
)
from app.services.itsm_service import ITSMService


router = APIRouter(
    prefix="/itsm",
    tags=["BMC Helix ITSM"],
)

# Alias router for "istm" spelling (hidden from OpenAPI schema to prevent duplicate routes)
istm_router = APIRouter(
    prefix="/istm",
    tags=["BMC Helix ITSM"],
)


def get_itsm_service(
    db: Session = Depends(get_db),
) -> ITSMService:
    """Create the ITSM service for the current request."""
    return ITSMService(db)


@router.get(
    "/changes",
    response_model=ITSMChangeListResponse,
    summary="List change requests",
)
def list_changes(
    limit: int = Query(default=100, ge=1, le=50000, description="Max changes to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status (Draft, Pending Approval, Scheduled, etc.)"),
    service: ITSMService = Depends(get_itsm_service),
):
    """List change requests. Automatically serves live BMC Helix ITSM API data if configured, or local/JSON data."""
    return service.list_changes(
        limit=limit,
        offset=offset,
        status=status_filter,
    )


@router.post(
    "/changes",
    response_model=ITSMChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create change request (19 BRD QA Fields)",
)
def create_change(
    payload: ITSMChangeCreate,
    service: ITSMService = Depends(get_itsm_service),
):
    """Create a change request with the 19 BRD Appendix D QA fields.

    Submits to BMC Helix ITSM QA API if configured, otherwise persists locally.
    """
    try:
        return service.create_change(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The change conflicts with an existing record or database constraint",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create ITSM change",
        ) from None


@router.get(
    "/changes/{change_id}",
    response_model=ITSMChangeResponse,
    summary="Get change request details by ID",
)
def get_change(
    change_id: int,
    service: ITSMService = Depends(get_itsm_service),
):
    """Retrieve change request details by database ID."""
    if change_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="change_id must be greater than zero",
        )

    change = service.get_change(change_id)
    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ITSM change not found",
        )
    return change


@router.patch(
    "/changes/{change_id}",
    response_model=ITSMChangeResponse,
    summary="Update change request attributes or status",
)
def update_change(
    change_id: int,
    payload: ITSMChangeUpdate,
    service: ITSMService = Depends(get_itsm_service),
):
    """Update selected attributes or status of a change request."""
    if change_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="change_id must be greater than zero",
        )
    try:
        updated = service.update_change(change_id, payload)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ITSM change not found",
            )
        return updated
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/changes/{change_id}/worklogs",
    response_model=ITSMWorklogListResponse,
    summary="List worklogs for a change request",
)
def list_change_worklogs(
    change_id: int,
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    service: ITSMService = Depends(get_itsm_service),
):
    """List worklogs associated with a specific change request."""
    return service.list_worklogs(change_id=change_id, limit=limit, offset=offset)


@router.post(
    "/changes/{change_id}/worklogs",
    response_model=ITSMWorklogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add worklog to a change request",
)
def create_change_worklog(
    change_id: int,
    payload: ITSMWorklogCreate,
    service: ITSMService = Depends(get_itsm_service),
):
    """Create a worklog entry for a change request."""
    try:
        return service.create_worklog(change_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/import",
    response_model=ITSMImportResponse,
    summary="Import and synchronize changes and worklogs into PostgreSQL",
)
def import_itsm_data(
    service: ITSMService = Depends(get_itsm_service),
) -> dict[str, Any]:
    """Synchronize change requests and worklogs into PostgreSQL from active source (API or JSON fixtures)."""
    return service.import_provider_changes()


# ======================================================================
# Forward all endpoints to the /istm alias router (hidden from OpenAPI schema)
# ======================================================================
istm_router.add_api_route("/changes", list_changes, methods=["GET"], response_model=ITSMChangeListResponse, include_in_schema=False)
istm_router.add_api_route("/changes", create_change, methods=["POST"], response_model=ITSMChangeResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
istm_router.add_api_route("/changes/{change_id}", get_change, methods=["GET"], response_model=ITSMChangeResponse, include_in_schema=False)
istm_router.add_api_route("/changes/{change_id}/worklogs", list_change_worklogs, methods=["GET"], response_model=ITSMWorklogListResponse, include_in_schema=False)
istm_router.add_api_route("/changes/{change_id}/worklogs", create_change_worklog, methods=["POST"], response_model=ITSMWorklogResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
istm_router.add_api_route("/import", import_itsm_data, methods=["POST"], response_model=ITSMImportResponse, include_in_schema=False)