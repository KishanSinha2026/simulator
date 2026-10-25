"""FastAPI endpoints for Red Hat Satellite hosts and job runs."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.satellite import (
    SatelliteHostResponse,
    SatelliteJobLaunchRequest,
    SatelliteJobRunResponse,
    SatelliteJobTemplateResponse,
)
from app.services.satellite_service import SatelliteService

router = APIRouter(prefix="/satellite", tags=["Red Hat Satellite"])


def get_satellite_service(
    db: Session = Depends(get_db),
) -> SatelliteService:
    """Create the Satellite service for the current request."""
    return SatelliteService(db)


@router.get("/hosts", response_model=PaginatedResponse)
def list_hosts(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SatelliteService = Depends(get_satellite_service),
):
    """List Satellite hosts stored in PostgreSQL."""
    return service.list_hosts(limit=limit, offset=offset)


@router.get(
    "/hosts/{host_id}",
    response_model=SatelliteHostResponse,
)
def get_host(
    host_id: int,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Retrieve a Satellite host by database ID."""
    host = service.get_host(host_id)

    if host is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Satellite host not found",
        )

    return host


@router.get(
    "/job-templates",
    response_model=PaginatedResponse,
)
def list_job_templates(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SatelliteService = Depends(get_satellite_service),
):
    """List job templates stored in PostgreSQL."""
    return service.list_job_templates(limit=limit, offset=offset)


@router.post(
    "/jobs",
    status_code=status.HTTP_202_ACCEPTED,
)
def launch_simulated_job(
    payload: SatelliteJobLaunchRequest,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Record a simulated job request without executing a remote job."""
    try:
        return service.launch_simulated_job(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to record simulated Satellite job",
        ) from None


@router.get(
    "/jobs/{job_run_id}",
    response_model=SatelliteJobRunResponse,
)
def get_job_run(
    job_run_id: int,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Retrieve a job run by database ID."""
    job = service.get_job_run(job_run_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Satellite job run not found",
        )

    return job