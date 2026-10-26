"""FastAPI endpoints for BMC Helix ITSM (and ISTM alias) change requests and worklogs."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.itsm import (
    ITSMChangeCreate,
    ITSMChangeHistoryListResponse,
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

# Alias router for "istm" spelling as requested in user prompt
istm_router = APIRouter(
    prefix="/istm",
    tags=["BMC Helix ITSM (Alias)"],
)


def get_itsm_service(
    db: Session = Depends(get_db),
) -> ITSMService:
    """Create the ITSM service for the current request."""
    return ITSMService(db)


# ======================================================================
# Change Request Routes (Database)
# ======================================================================


@router.get(
    "/changes",
    response_model=ITSMChangeListResponse,
)
def list_changes(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    service: ITSMService = Depends(get_itsm_service),
):
    """List persisted ITSM change requests from PostgreSQL."""
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
    """Retrieve an ITSM change by its database ID."""
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


@router.post(
    "/changes",
    response_model=ITSMChangeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_change(
    payload: ITSMChangeCreate,
    service: ITSMService = Depends(get_itsm_service),
):
    """Create a simulated ITSM change request in PostgreSQL."""
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
            detail=(
                "The change conflicts with an existing record "
                "or violates a database constraint"
            ),
        ) from None

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
    """Update selected fields on an existing ITSM change."""
    if change_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="change_id must be greater than zero",
        )

    try:
        change = service.update_change(change_id, payload)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The update violates a database constraint",
        ) from None

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


# ======================================================================
# Worklog Routes (Database)
# ======================================================================


@router.get(
    "/changes/{change_id}/worklogs",
    response_model=ITSMWorklogListResponse,
)
def list_change_worklogs(
    change_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ITSMService = Depends(get_itsm_service),
):
    """List worklogs associated with a specific change request."""
    return service.list_worklogs(change_id=change_id, limit=limit, offset=offset)


@router.post(
    "/changes/{change_id}/worklogs",
    response_model=ITSMWorklogResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_change_worklog(
    change_id: int,
    payload: ITSMWorklogCreate,
    service: ITSMService = Depends(get_itsm_service),
):
    """Create a worklog entry for a change request in PostgreSQL."""
    try:
        return service.create_worklog(change_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/worklogs",
    response_model=ITSMWorklogListResponse,
)
def list_all_worklogs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ITSMService = Depends(get_itsm_service),
):
    """List all worklog entries from PostgreSQL."""
    return service.list_worklogs(limit=limit, offset=offset)


@router.get(
    "/worklogs/{worklog_id}",
    response_model=ITSMWorklogResponse,
)
def get_worklog(
    worklog_id: int,
    service: ITSMService = Depends(get_itsm_service),
):
    """Retrieve a worklog by internal ID."""
    worklog = service.get_worklog(worklog_id)
    if worklog is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worklog not found",
        )
    return worklog


# ======================================================================
# History Routes (Database)
# ======================================================================


@router.get(
    "/changes/{change_id}/history",
    response_model=ITSMChangeHistoryListResponse,
)
def list_change_history(
    change_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ITSMService = Depends(get_itsm_service),
):
    """List audit history entries for a change request."""
    return service.list_history(change_id=change_id, limit=limit, offset=offset)


# ======================================================================
# Data Import & Synchronization Route
# ======================================================================


@router.post(
    "/import",
    response_model=ITSMImportResponse,
)
def import_itsm_data(
    service: ITSMService = Depends(get_itsm_service),
):
    """Import changes and worklogs from active provider into PostgreSQL."""
    return service.import_provider_changes()


# ======================================================================
# Provider / JSON Aliases (Hidden from Swagger UI to prevent duplicates)
# ======================================================================


@router.get(
    "/provider/changes",
    include_in_schema=False,
)
def list_provider_changes(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    service: ITSMService = Depends(get_itsm_service),
) -> list[dict[str, Any]]:
    """Preview changes directly from the active provider."""
    filters = {"status": status} if status else None
    return service.list_provider_changes(limit=limit, offset=offset, filters=filters)


@router.get(
    "/provider/worklogs",
    include_in_schema=False,
)
def list_provider_worklogs(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: ITSMService = Depends(get_itsm_service),
) -> list[dict[str, Any]]:
    """Preview worklogs directly from the active provider."""
    return service.list_provider_worklogs(limit=limit, offset=offset)


@router.post(
    "/provider/changes",
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_provider_change(
    payload: dict[str, Any],
    service: ITSMService = Depends(get_itsm_service),
) -> dict[str, Any]:
    """Create a simulated change directly in the active JSON provider."""
    return service.create_provider_change(payload)


@router.post(
    "/provider/import",
    response_model=ITSMImportResponse,
    include_in_schema=False,
)
def import_provider_changes_alias(
    service: ITSMService = Depends(get_itsm_service),
):
    """Alias for /import preserving backwards compatibility."""
    return service.import_provider_changes()



# ======================================================================
# ISTM Router Alias Setup (Forwarding all endpoints to /istm)
# ======================================================================
istm_router.add_api_route("/changes", list_changes, methods=["GET"], response_model=ITSMChangeListResponse)
istm_router.add_api_route("/changes/{change_id}", get_change, methods=["GET"], response_model=ITSMChangeResponse)
istm_router.add_api_route("/changes", create_change, methods=["POST"], response_model=ITSMChangeResponse, status_code=status.HTTP_201_CREATED)
istm_router.add_api_route("/changes/{change_id}", update_change, methods=["PATCH"], response_model=ITSMChangeResponse)
istm_router.add_api_route("/changes/{change_id}/worklogs", list_change_worklogs, methods=["GET"], response_model=ITSMWorklogListResponse)
istm_router.add_api_route("/changes/{change_id}/worklogs", create_change_worklog, methods=["POST"], response_model=ITSMWorklogResponse, status_code=status.HTTP_201_CREATED)
istm_router.add_api_route("/worklogs", list_all_worklogs, methods=["GET"], response_model=ITSMWorklogListResponse)
istm_router.add_api_route("/worklogs/{worklog_id}", get_worklog, methods=["GET"], response_model=ITSMWorklogResponse)
istm_router.add_api_route("/changes/{change_id}/history", list_change_history, methods=["GET"], response_model=ITSMChangeHistoryListResponse)
istm_router.add_api_route("/provider/changes", list_provider_changes, methods=["GET"])
istm_router.add_api_route("/provider/worklogs", list_provider_worklogs, methods=["GET"])
istm_router.add_api_route("/provider/changes", create_provider_change, methods=["POST"], status_code=status.HTTP_201_CREATED)
istm_router.add_api_route("/provider/import", import_provider_changes_alias, methods=["POST"], response_model=ITSMImportResponse)
istm_router.add_api_route("/import", import_itsm_data, methods=["POST"], response_model=ITSMImportResponse)