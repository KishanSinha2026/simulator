"""FastAPI endpoints for BMC Helix CMDB server configuration items."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cmdb import (
    CMDBServerCreate,
    CMDBServerResponse,
    CMDBServerUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.cmdb_service import CMDBService


router = APIRouter(
    prefix="/cmdb",
    tags=["BMC Helix CMDB"],
)


def get_cmdb_service(
    db: Session = Depends(get_db),
) -> CMDBService:
    """Create the CMDB service for the current request."""
    return CMDBService(db)


@router.get(
    "/servers",
    response_model=PaginatedResponse,
)
def list_servers(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    ip_address: str | None = Query(default=None, min_length=1, max_length=45),
    service: CMDBService = Depends(get_cmdb_service),
):
    """List persisted server CIs with optional filters."""
    return service.list_servers(
        limit=limit,
        offset=offset,
        status=status_filter,
        ip_address=ip_address,
    )


@router.get(
    "/servers/by-ip/{ip_address}",
    response_model=list[CMDBServerResponse],
)
def find_servers_by_ip(
    ip_address: str,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Return all server CIs matching an IP address."""
    try:
        return service.find_servers_by_ip(ip_address)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/servers/{server_id}",
    response_model=CMDBServerResponse,
)
def get_server(
    server_id: int,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Retrieve a server CI by its internal database ID."""
    if server_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="server_id must be greater than zero",
        )

    server = service.get_server(server_id)

    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CMDB server not found",
        )

    return server


@router.post(
    "/servers",
    response_model=CMDBServerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_server(
    payload: CMDBServerCreate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Create a simulated CMDB server record in PostgreSQL."""
    try:
        return service.create_server(payload)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A CMDB record with this source instance ID "
                "already exists or violates a database constraint"
            ),
        ) from None

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create CMDB server",
        ) from None


@router.patch(
    "/servers/{server_id}",
    response_model=CMDBServerResponse,
)
def update_server(
    server_id: int,
    payload: CMDBServerUpdate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Update selected fields on an existing server CI."""
    if server_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="server_id must be greater than zero",
        )

    try:
        server = service.update_server(server_id, payload)

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
            detail="Unable to update CMDB server",
        ) from None

    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CMDB server not found",
        )

    return server