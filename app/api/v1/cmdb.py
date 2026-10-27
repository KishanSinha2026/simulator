"""FastAPI endpoints for BMC Helix CMDB configuration items.

Implements unified BRD Section 4.3 routes:
- GET /servers (server CI inventory with optional status/IP filters)
- POST /servers (create/upsert server CI)
- GET /servers/{server_id} (server CI details)
- PATCH /servers/{server_id} (update server CI attributes/writeback)
- GET /correlate (correlate by ?ip_address=...)
- GET /correlate/{ip_address} (BRD 4.3 IP-to-CI correlation rule: MATCHED, CMDB_NOT_FOUND, AMBIGUOUS_MATCH, CMDB_CI_INACTIVE)
- GET /middleware (list middleware CIs)
- GET /databases (list database CIs)
- GET /relationships (list CI relationships)
- POST /import (synchronize/import CMDB configuration items into PostgreSQL)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cmdb import (
    CMDBDatabaseListResponse,
    CMDBImportResponse,
    CMDBLookupResponse,
    CMDBMiddlewareListResponse,
    CMDBRelationshipListResponse,
    CMDBServerCreate,
    CMDBServerListResponse,
    CMDBServerResponse,
    CMDBServerUpdate,
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
    limit: int = Query(default=100, ge=1, le=50000, description="Max servers to return"),
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


@router.post(
    "/servers",
    response_model=CMDBServerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update server CI",
)
def create_server(
    payload: CMDBServerCreate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Idempotently create or update a server CI record."""
    try:
        return service.create_server(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


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


@router.patch(
    "/servers/{server_id}",
    response_model=CMDBServerResponse,
    summary="Update server CI (patch writeback)",
)
def update_server(
    server_id: int,
    payload: CMDBServerUpdate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Update selected attributes on an existing server CI (e.g. OS version and patch timestamp)."""
    if server_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="server_id must be greater than zero",
        )
    try:
        updated = service.update_server(server_id, payload)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CMDB server not found",
            )
        return updated
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/correlate",
    response_model=CMDBLookupResponse,
    summary="Correlate IP address to server CI via query parameter (BRD Rule 4.3)",
)
def correlate_ip_query(
    ip_address: str = Query(..., min_length=1, max_length=45, description="IP address to correlate"),
    service: CMDBService = Depends(get_cmdb_service),
):
    """Correlate IP address using query parameter according to BRD Section 4.3."""
    try:
        return service.correlate_ip(ip_address)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


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


@router.get(
    "/middleware",
    response_model=CMDBMiddlewareListResponse,
    summary="List middleware configuration items",
)
def list_middleware(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    middleware_type: str | None = Query(default=None),
    service: CMDBService = Depends(get_cmdb_service),
) -> dict[str, Any]:
    """List persisted middleware CIs matching Appendix C fields."""
    try:
        return service.list_middleware(limit=limit, offset=offset, middleware_type=middleware_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/databases",
    response_model=CMDBDatabaseListResponse,
    summary="List database configuration items",
)
def list_databases(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    database_type: str | None = Query(default=None),
    service: CMDBService = Depends(get_cmdb_service),
) -> dict[str, Any]:
    """List persisted database CIs matching Appendix C fields."""
    try:
        return service.list_databases(limit=limit, offset=offset, database_type=database_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/relationships",
    response_model=CMDBRelationshipListResponse,
    summary="List CI relationships",
)
def list_relationships(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    service: CMDBService = Depends(get_cmdb_service),
) -> dict[str, Any]:
    """List persisted CI relationships."""
    try:
        return service.list_relationships(limit=limit, offset=offset)
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