"""FastAPI endpoints for SCCM 2509 Windows execution and patch deployments.

Implements unified BRD Section 4.6 & Section 8.5.5 routes:
- GET /devices (list devices and check client active readiness gate)
- GET /devices/{device_id} (read device details)
- GET /collections (list approved target collections)
- GET /deployments (list update group assignments / deployment policies)
- POST /jobs (launch guarded patch execution run with targets array)
- GET /jobs/{job_id} (poll deployment run status and compliance breakdown)
- GET /jobs (list deployment run history)
- POST /import (synchronize/import SCCM devices and collections into PostgreSQL)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.sccm import (
    SCCMCollectionListResponse,
    SCCMDeploymentListResponse,
    SCCMDeploymentRunListResponse,
    SCCMDeploymentRunResponse,
    SCCMDeviceListResponse,
    SCCMDeviceResponse,
    SCCMImportResponse,
    SCCMJobLaunchRequest,
)
from app.services.sccm_service import SCCMService


router = APIRouter(
    prefix="/sccm",
    tags=["SCCM 2509"],
)


def get_sccm_service(
    db: Session = Depends(get_db),
) -> SCCMService:
    """Create SCCM service for current request."""
    return SCCMService(db)


@router.get(
    "/devices",
    response_model=SCCMDeviceListResponse,
    summary="List Configuration Manager devices (BRD Table 20)",
)
def list_devices(
    limit: int = Query(default=100, ge=1, le=50000, description="Max devices to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    collection_id: str | None = Query(default=None, description="Filter by CollectionID"),
    service: SCCMService = Depends(get_sccm_service),
) -> dict[str, Any]:
    """List devices and verify ClientActiveStatus readiness gate. Serves live API or local/JSON data."""
    try:
        return service.list_devices(limit=limit, offset=offset, collection_id=collection_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/devices/{device_id}",
    response_model=SCCMDeviceResponse,
    summary="Get device details by ID",
)
def get_device(
    device_id: int,
    service: SCCMService = Depends(get_sccm_service),
):
    """Retrieve device record by database ID."""
    if device_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="device_id must be greater than zero",
        )
    device = service.get_device(device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SCCM device not found",
        )
    return device


@router.get(
    "/collections",
    response_model=SCCMCollectionListResponse,
    summary="List approved device collections (BRD Table 20)",
)
def list_collections(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    service: SCCMService = Depends(get_sccm_service),
) -> dict[str, Any]:
    """Retrieve approved device collections."""
    try:
        return service.list_collections(limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/deployments",
    response_model=SCCMDeploymentListResponse,
    summary="List update group deployment policies",
)
def list_deployments(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    service: SCCMService = Depends(get_sccm_service),
) -> dict[str, Any]:
    """Retrieve software update group deployments and maintenance windows."""
    try:
        return service.list_deployments(limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/jobs",
    response_model=SCCMDeploymentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Launch guarded patch execution run (BRD Section 8.5.5)",
)
def launch_job(
    payload: SCCMJobLaunchRequest,
    service: SCCMService = Depends(get_sccm_service),
):
    """Launch and record a guarded SCCM patch deployment execution run."""
    try:
        return service.launch_deployment_run(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/jobs",
    response_model=SCCMDeploymentRunListResponse,
    summary="List deployment runs",
)
def list_jobs(
    limit: int = Query(default=100, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    service: SCCMService = Depends(get_sccm_service),
) -> dict[str, Any]:
    """List deployment execution runs."""
    try:
        return service.list_deployment_runs(limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/jobs/{job_id}",
    response_model=SCCMDeploymentRunResponse,
    summary="Get deployment run status and compliance details (BRD Section 4.6)",
)
def get_job(
    job_id: str,
    service: SCCMService = Depends(get_sccm_service),
):
    """Poll deployment run compliance status: compliant, in_progress, error, unknown, skipped."""
    run = service.get_deployment_run(job_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SCCM deployment run not found",
        )
    return run


@router.post(
    "/import",
    response_model=SCCMImportResponse,
    summary="Import and synchronize SCCM devices and collections into PostgreSQL",
)
def import_sccm_data(
    service: SCCMService = Depends(get_sccm_service),
) -> dict[str, Any]:
    """Synchronize devices, collections, and deployments into PostgreSQL from active source."""
    return service.import_provider_data()
