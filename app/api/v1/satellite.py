"""FastAPI endpoints for Red Hat Satellite hosts, job templates, and execution.

Implements unified BRD Section 4.5 routes:
- GET /hosts (S1: Inventory hosts registered in Satellite)
- GET /job-templates (S2: Approved Ansible/Satellite execution job templates)
- POST /jobs (S3: Launch job invocation with template_id, host_ids, inputs)
- GET /jobs/{job_run_id} (S4/S5: Read job status and host execution results)
- POST /jobs/{job_run_id}/cancel (S7: Policy-approved job cancellation)
- POST /import (synchronize/import hosts and job templates into PostgreSQL)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.satellite import (
    SatelliteHostListResponse,
    SatelliteImportResponse,
    SatelliteJobCancelRequest,
    SatelliteJobLaunchRequest,
    SatelliteJobRunResponse,
    SatelliteJobTemplateListResponse,
)
from app.services.satellite_service import SatelliteService


router = APIRouter(
    prefix="/satellite",
    tags=["Red Hat Satellite"],
)


def get_satellite_service(
    db: Session = Depends(get_db),
) -> SatelliteService:
    """Create the Satellite service for the current request."""
    return SatelliteService(db)


@router.get(
    "/hosts",
    response_model=SatelliteHostListResponse,
    summary="List Satellite hosts (BRD S1)",
)
def list_hosts(
    limit: int = Query(default=100, ge=1, le=500, description="Max hosts to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """Retrieve hosts managed by Satellite. Serves live API data if configured, or local/JSON data."""
    return service.list_hosts(
        limit=limit,
        offset=offset,
    )


@router.get(
    "/job-templates",
    response_model=SatelliteJobTemplateListResponse,
    summary="List approved job templates (BRD S2)",
)
def list_job_templates(
    limit: int = Query(default=100, ge=1, le=500, description="Max templates to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """Retrieve approved Satellite/Ansible job templates."""
    return service.list_job_templates(
        limit=limit,
        offset=offset,
    )


@router.post(
    "/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Launch job execution (BRD S3)",
)
def launch_job(
    payload: SatelliteJobLaunchRequest,
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """Launch execution of an approved job template on selected target hosts.

    Dispatches to Red Hat Satellite API if configured, otherwise records simulated run.
    """
    try:
        return service.launch_simulated_job(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The job conflicts with a database constraint",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to launch Satellite job",
        ) from None


@router.get(
    "/jobs/{job_run_id}",
    response_model=SatelliteJobRunResponse,
    summary="Get job run status and results (BRD S4/S5)",
)
def get_job_run(
    job_run_id: int,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Poll job run status, completion timestamps, and host execution outputs."""
    if job_run_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="job_run_id must be greater than zero",
        )

    job = service.get_job_run(job_run_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Satellite job run not found",
        )
    return job


@router.post(
    "/jobs/{job_run_id}/cancel",
    response_model=SatelliteJobRunResponse,
    summary="Cancel active job run (BRD S7)",
)
def cancel_job_run(
    job_run_id: int,
    payload: SatelliteJobCancelRequest,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Cancel a pending or active job run per bank operational policy."""
    try:
        return service.cancel_job_run(job_run_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/import",
    response_model=SatelliteImportResponse,
    summary="Import and synchronize hosts and templates into PostgreSQL",
)
def import_satellite_data(
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """Synchronize hosts and job templates into PostgreSQL from active source (API or JSON fixtures)."""
    return service.import_provider_data()