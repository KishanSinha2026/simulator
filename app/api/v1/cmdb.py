"""FastAPI endpoints for BMC Helix CMDB server, middleware, database, and relationship CIs."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cmdb import (
    CMDBDatabaseCreate,
    CMDBDatabaseListResponse,
    CMDBDatabaseResponse,
    CMDBDatabaseUpdate,
    CMDBImportResponse,
    CMDBLookupResponse,
    CMDBMiddlewareCreate,
    CMDBMiddlewareListResponse,
    CMDBMiddlewareResponse,
    CMDBMiddlewareUpdate,
    CMDBRelationshipCreate,
    CMDBRelationshipListResponse,
    CMDBRelationshipResponse,
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


# ======================================================================
# Server CI Routes (Database)
# ======================================================================


@router.get(
    "/servers",
    response_model=CMDBServerListResponse,
)
def list_servers(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    ip_address: str | None = Query(default=None, min_length=1, max_length=45),
    service: CMDBService = Depends(get_cmdb_service),
):
    """List persisted server CIs from PostgreSQL with optional filters."""
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
    """Return all server CIs matching an IP address from PostgreSQL."""
    try:
        return service.find_servers_by_ip(ip_address)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/correlate/{ip_address}",
    response_model=CMDBLookupResponse,
)
def correlate_ip(
    ip_address: str,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Correlate IP address to server CI using BRD Section 4.3 rules.

    Returns correlation_outcome:
    MATCHED, CMDB_NOT_FOUND, AMBIGUOUS_MATCH, CMDB_CI_INACTIVE
    """
    try:
        return service.correlate_ip(ip_address)
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


# ======================================================================
# Middleware CI Routes (Database)
# ======================================================================


@router.get(
    "/middleware",
    response_model=CMDBMiddlewareListResponse,
)
def list_middleware(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    middleware_type: str | None = Query(default=None),
    service: CMDBService = Depends(get_cmdb_service),
):
    """List persisted middleware CIs from PostgreSQL."""
    return service.list_middleware(
        limit=limit,
        offset=offset,
        middleware_type=middleware_type,
    )


@router.get(
    "/middleware/{middleware_id}",
    response_model=CMDBMiddlewareResponse,
)
def get_middleware(
    middleware_id: int,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Retrieve a middleware CI by its database ID."""
    if middleware_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="middleware_id must be greater than zero",
        )

    middleware = service.get_middleware(middleware_id)
    if middleware is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CMDB middleware not found",
        )
    return middleware


@router.post(
    "/middleware",
    response_model=CMDBMiddlewareResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_middleware(
    payload: CMDBMiddlewareCreate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Create a middleware CI in PostgreSQL."""
    try:
        return service.create_middleware(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Middleware with this instance ID already exists",
        ) from None


@router.patch(
    "/middleware/{middleware_id}",
    response_model=CMDBMiddlewareResponse,
)
def update_middleware(
    middleware_id: int,
    payload: CMDBMiddlewareUpdate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Update selected fields on a middleware CI."""
    record = service.update_middleware(middleware_id, payload)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CMDB middleware not found",
        )
    return record


# ======================================================================
# Database CI Routes (Database)
# ======================================================================


@router.get(
    "/databases",
    response_model=CMDBDatabaseListResponse,
)
def list_databases(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    database_type: str | None = Query(default=None),
    service: CMDBService = Depends(get_cmdb_service),
):
    """List persisted database CIs from PostgreSQL."""
    return service.list_databases(
        limit=limit,
        offset=offset,
        database_type=database_type,
    )


@router.get(
    "/databases/{database_id}",
    response_model=CMDBDatabaseResponse,
)
def get_database(
    database_id: int,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Retrieve a database CI by its database ID."""
    if database_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="database_id must be greater than zero",
        )

    db_record = service.get_database(database_id)
    if db_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CMDB database not found",
        )
    return db_record


@router.post(
    "/databases",
    response_model=CMDBDatabaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_database(
    payload: CMDBDatabaseCreate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Create a database CI in PostgreSQL."""
    try:
        return service.create_database(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database CI with this instance ID already exists",
        ) from None


@router.patch(
    "/databases/{database_id}",
    response_model=CMDBDatabaseResponse,
)
def update_database(
    database_id: int,
    payload: CMDBDatabaseUpdate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Update selected fields on a database CI."""
    record = service.update_database(database_id, payload)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CMDB database not found",
        )
    return record


# ======================================================================
# Relationship Routes (Database)
# ======================================================================


@router.get(
    "/relationships",
    response_model=CMDBRelationshipListResponse,
)
def list_relationships(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: CMDBService = Depends(get_cmdb_service),
):
    """List relationships between CMDB CIs in PostgreSQL."""
    return service.list_relationships(limit=limit, offset=offset)


@router.get(
    "/relationships/{relationship_id}",
    response_model=CMDBRelationshipResponse,
)
def get_relationship(
    relationship_id: int,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Retrieve a relationship by internal ID."""
    record = service.get_relationship(relationship_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CMDB relationship not found",
        )
    return record


@router.post(
    "/relationships",
    response_model=CMDBRelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    payload: CMDBRelationshipCreate,
    service: CMDBService = Depends(get_cmdb_service),
):
    """Create a relationship in PostgreSQL."""
    try:
        return service.create_relationship(payload)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relationship already exists or violates constraint",
        ) from None


# ======================================================================
# Data Import & Synchronization Route
# ======================================================================


@router.post(
    "/import",
    response_model=CMDBImportResponse,
)
def import_cmdb_data(
    service: CMDBService = Depends(get_cmdb_service),
):
    """Import servers, middleware, and databases from the active provider into PostgreSQL."""
    return service.import_provider_data()


# ======================================================================
# Provider / JSON Aliases (Hidden from Swagger UI to prevent duplicates)
# ======================================================================


@router.get(
    "/provider/servers",
    include_in_schema=False,
)
def list_provider_servers(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    service: CMDBService = Depends(get_cmdb_service),
) -> list[dict[str, Any]]:
    """Preview server CIs directly from the active provider."""
    filters = {"status": status} if status else None
    return service.list_provider_servers(limit=limit, offset=offset, filters=filters)


@router.get(
    "/provider/middleware",
    include_in_schema=False,
)
def list_provider_middleware(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: CMDBService = Depends(get_cmdb_service),
) -> list[dict[str, Any]]:
    """Preview middleware CIs directly from the active provider."""
    return service.list_provider_middleware(limit=limit, offset=offset)


@router.get(
    "/provider/databases",
    include_in_schema=False,
)
def list_provider_databases(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: CMDBService = Depends(get_cmdb_service),
) -> list[dict[str, Any]]:
    """Preview database CIs directly from the active provider."""
    return service.list_provider_databases(limit=limit, offset=offset)


@router.get(
    "/provider/by-ip/{ip_address}",
    include_in_schema=False,
)
def find_provider_servers_by_ip(
    ip_address: str,
    service: CMDBService = Depends(get_cmdb_service),
) -> list[dict[str, Any]]:
    """Find servers by IP address in the active provider."""
    return service.find_provider_servers_by_ip(ip_address)


@router.post(
    "/provider/servers",
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_provider_server(
    payload: dict[str, Any],
    service: CMDBService = Depends(get_cmdb_service),
) -> dict[str, Any]:
    """Create a server CI directly in the JSON fixture provider."""
    return service.create_provider_server(payload)


@router.post(
    "/provider/import",
    response_model=CMDBImportResponse,
    include_in_schema=False,
)
def import_provider_data_alias(
    service: CMDBService = Depends(get_cmdb_service),
):
    """Alias for /import preserving backwards compatibility."""
    return service.import_provider_data()