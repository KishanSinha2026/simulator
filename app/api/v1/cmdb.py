"""FastAPI endpoints for BMC Helix CMDB configuration items.

Implements unified BRD Section 4.3 routes:
- GET /servers (server CI inventory with optional status/IP filters)
- GET /servers/{server_id} (server CI details)
- GET /correlate/{ip_address} (BRD 4.3 IP-to-CI correlation rule: MATCHED, CMDB_NOT_FOUND, AMBIGUOUS_MATCH, CMDB_CI_INACTIVE)
- POST /import (synchronize/import CMDB configuration items into PostgreSQL)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cmdb import (
    CMDBImportResponse,
    CMDBLookupResponse,
    CMDBServerListResponse,
    CMDBServerResponse,
)
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
    response_model=CMDBServerListResponse,
    summary="List server configuration items",
)
def list_servers(
    limit: int = Query(default=100, ge=1, le=500, description="Max servers to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status (Active, Inactive, etc.)"),
    ip_address: str | None = Query(default=None, min_length=1, max_length=45, description="Filter by exact IP address"),
    service: CMDBService = Depends(get_cmdb_service),
):
    """List server CIs. Automatically serves live BMC Helix CMDB API data if configured, or local/JSON data."""
    return service.list_servers(
        limit=limit,
        offset=offset,
        status=status_filter,
        ip_address=ip_address,
    )


@router.get(
    "/servers/{server_id}",
    response_model=CMDBServerResponse,
    summary="Get server CI details by ID",
)
def get_server(
    server_id: int,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Retrieve server CI details including attributes, environment, and ownership."""
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


@router.get(
    "/correlate/{ip_address}",
    response_model=CMDBLookupResponse,
    summary="Correlate IP address to server CI (BRD Rule 4.3)",
)
def correlate_ip(
    ip_address: str,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Correlate IP address to server CI using BRD Section 4.3 rules.

    Returns correlation_outcome:
    - MATCHED: Exactly one eligible active server found.
    - CMDB_NOT_FOUND: No CI matched for IP; held for delta reporting.
    - AMBIGUOUS_MATCH: Multiple CIs found for IP; held for manual review.
    - CMDB_CI_INACTIVE: Server CI is inactive/decommissioned; held from automated patching.
    """
    try:
        return service.correlate_ip(ip_address)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/import",
    response_model=CMDBImportResponse,
    summary="Import and synchronize CMDB CIs into PostgreSQL",
)
def import_cmdb_data(
    service: CMDBService = Depends(get_cmdb_service),
) -> dict[str, Any]:
    """Synchronize server, middleware, and database CIs into PostgreSQL from active source (API or JSON fixtures)."""
    return service.import_provider_data()