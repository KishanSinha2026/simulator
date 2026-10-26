"""FastAPI endpoints for Red Hat Satellite hosts, job templates, and job simulation."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.satellite import (
    SatelliteHostCreate,
    SatelliteHostListResponse,
    SatelliteHostResponse,
    SatelliteHostUpdate,
    SatelliteImportResponse,
    SatelliteJobCancelRequest,
    SatelliteJobHostResultListResponse,
    SatelliteJobHostResultResponse,
    SatelliteJobLaunchRequest,
    SatelliteJobRunListResponse,
    SatelliteJobRunResponse,
    SatelliteJobTemplateCreate,
    SatelliteJobTemplateListResponse,
    SatelliteJobTemplateResponse,
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


# ======================================================================
# Host Routes (Database)
# ======================================================================


@router.get(
    "/hosts",
    response_model=SatelliteHostListResponse,
)
def list_hosts(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """List Satellite hosts stored in PostgreSQL."""
    return service.list_hosts(
        limit=limit,
        offset=offset,
    )


@router.get(
    "/hosts/{host_id}",
    response_model=SatelliteHostResponse,
)
def get_host(
    host_id: int,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Retrieve a host using its internal database ID."""
    if host_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="host_id must be greater than zero",
        )

    host = service.get_host(host_id)

    if host is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Satellite host not found",
        )

    return host


@router.post(
    "/hosts",
    response_model=SatelliteHostResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_host(
    payload: SatelliteHostCreate,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Create a Satellite host in PostgreSQL."""
    try:
        return service.create_host(payload)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Host with this source_host_id already exists",
        ) from None


@router.patch(
    "/hosts/{host_id}",
    response_model=SatelliteHostResponse,
)
def update_host(
    host_id: int,
    payload: SatelliteHostUpdate,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Update selected fields on a Satellite host."""
    host = service.update_host(host_id, payload)
    if host is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Satellite host not found",
        )
    return host


# ======================================================================
# Job Template Routes (Database)
# ======================================================================


@router.get(
    "/job-templates",
    response_model=SatelliteJobTemplateListResponse,
)
def list_job_templates(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """List job templates stored in PostgreSQL."""
    return service.list_job_templates(
        limit=limit,
        offset=offset,
    )


@router.get(
    "/job-templates/{template_id}",
    response_model=SatelliteJobTemplateResponse,
)
def get_job_template(
    template_id: int,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Retrieve a job template by internal database ID."""
    template = service.get_job_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Satellite job template not found",
        )
    return template


@router.post(
    "/job-templates",
    response_model=SatelliteJobTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job_template(
    payload: SatelliteJobTemplateCreate,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Create a job template in PostgreSQL."""
    try:
        return service.create_job_template(payload)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job template with this source_template_id already exists",
        ) from None


# ======================================================================
# Job Run & Execution Routes (Database)
# ======================================================================


@router.get(
    "/jobs",
    response_model=SatelliteJobRunListResponse,
)
def list_job_runs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    service: SatelliteService = Depends(get_satellite_service),
):
    """List job runs stored in PostgreSQL."""
    return service.list_job_runs(limit=limit, offset=offset, status=status_filter)


@router.post(
    "/jobs",
    status_code=status.HTTP_202_ACCEPTED,
)
def launch_simulated_job(
    payload: SatelliteJobLaunchRequest,
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """Record a simulated job request in PostgreSQL without launching a remote job."""
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
            detail="The simulated job conflicts with a database constraint",
        ) from None

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
    """Retrieve a job run using its internal database ID."""
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
)
def cancel_job_run(
    job_run_id: int,
    payload: SatelliteJobCancelRequest,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Cancel a pending simulated job run."""
    try:
        return service.cancel_job_run(job_run_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/jobs/{job_run_id}/hosts",
    response_model=SatelliteJobHostResultListResponse,
)
def list_host_results(
    job_run_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SatelliteService = Depends(get_satellite_service),
):
    """List host completion results for a job run."""
    return service.list_host_results(job_run_id, limit=limit, offset=offset)


@router.get(
    "/jobs/{job_run_id}/hosts/{host_id}",
    response_model=SatelliteJobHostResultResponse,
)
def get_host_result(
    job_run_id: int,
    host_id: int,
    service: SatelliteService = Depends(get_satellite_service),
):
    """Retrieve host completion result for a specific host in a job run."""
    result = service.get_host_result(job_run_id, host_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Satellite host result not found",
        )
    return result


# ======================================================================
# Provider / JSON Data Routes (Mock & Live API integration)
# ======================================================================


@router.get(
    "/provider/hosts",
)
def list_provider_hosts(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: SatelliteService = Depends(get_satellite_service),
) -> list[dict[str, Any]]:
    """Preview hosts directly from the active provider (JSON fixture or Satellite API)."""
    return service.list_provider_hosts(limit=limit, offset=offset)


@router.get(
    "/provider/job-templates",
)
def list_provider_job_templates(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: SatelliteService = Depends(get_satellite_service),
) -> list[dict[str, Any]]:
    """Preview job templates directly from the active provider."""
    return service.list_provider_job_templates(limit=limit, offset=offset)


@router.get(
    "/provider/jobs",
)
def list_provider_job_runs(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    service: SatelliteService = Depends(get_satellite_service),
) -> list[dict[str, Any]]:
    """Preview job runs directly from the active provider."""
    return service.list_provider_job_runs(limit=limit, offset=offset)


@router.post(
    "/provider/hosts",
    status_code=status.HTTP_201_CREATED,
)
def create_provider_host(
    payload: dict[str, Any],
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """Create a host directly in the active JSON fixture provider."""
    try:
        return service.create_provider_host(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/provider/jobs",
    status_code=status.HTTP_202_ACCEPTED,
)
def launch_provider_job(
    payload: SatelliteJobLaunchRequest,
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """Launch or simulate a job directly using the active provider."""
    try:
        return service.launch_provider_job(
            template_id=payload.template_id,
            host_ids=payload.host_ids,
            inputs=payload.inputs,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/provider/jobs/{job_run_id}/cancel",
)
def cancel_provider_job(
    job_run_id: str,
    service: SatelliteService = Depends(get_satellite_service),
) -> dict[str, Any]:
    """Cancel a job directly via the active provider."""
    try:
        return service.cancel_provider_job(job_run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/provider/import",
    response_model=SatelliteImportResponse,
)
def import_provider_data(
    service: SatelliteService = Depends(get_satellite_service),
):
    """Import hosts and job templates from the active provider into PostgreSQL."""
    return service.import_provider_data()