"""Ansible Automation Platform job template and patch execution routes."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.ansible import AnsibleJobRun
from app.providers.factory import get_provider
from app.services.patching_guard import active_exception_targets
from app.schemas.ansible import (
    AnsibleConnectionResponse,
    AnsibleJobCancelResponse,
    AnsibleJobLaunchResponse,
    AnsibleJobRunResponse,
    AnsibleJobTemplateListResponse,
    AnsibleLaunchRequest,
)

router = APIRouter(prefix="/ansible", tags=["Ansible Automation"])

def _provider():
    if get_settings().ansible_provider != "api":
        raise HTTPException(status_code=503, detail="Ansible API provider is not enabled")
    try:
        return get_provider("ansible")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


@router.get("/job-templates", response_model=AnsibleJobTemplateListResponse)
def list_job_templates(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    try:
        data = _provider().list_templates(limit=limit, offset=offset)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"items": data.get("results", []), "count": data.get("count", 0), "next": data.get("next")}


@router.get("/connection", response_model=AnsibleConnectionResponse)
def test_connection() -> dict[str, Any]:
    """Check connectivity and API authentication without launching a job."""
    try:
        data = _provider().test_connection()
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "connected": True,
        "controller": data.get("name") or data.get("description"),
        "api_version": data.get("version"),
    }


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED, response_model=AnsibleJobLaunchResponse)
def launch_job(payload: AnsibleLaunchRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Launch an AWX/AAP job; this can execute patch changes on target hosts."""
    requested_targets = {target.strip() for target in payload.limit.split(",")}
    blocked = active_exception_targets(db, requested_targets)
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patch launch blocked because an active Squad1 exception applies to a target",
        )
    try:
        result = _provider().launch_job(payload.job_template_id, limit=payload.limit, extra_vars=payload.extra_vars)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    source_id = str(result.get("id", "")).strip()
    if not source_id:
        raise HTTPException(status_code=502, detail="Ansible launch response did not include a job ID")
    run = AnsibleJobRun(
        source_job_id=source_id,
        job_template_id=payload.job_template_id,
        status=str(result.get("status") or "pending"),
        limit=payload.limit,
        extra_vars=payload.extra_vars,
        source_payload=result,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"id": run.id, "job_id": run.source_job_id, "status": run.status, "job_template_id": run.job_template_id}


@router.get("/jobs/{job_id}", response_model=AnsibleJobRunResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.get(AnsibleJobRun, job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ansible job run not found")
    try:
        data = _provider().get_job(run.source_job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    run.status = str(data.get("status") or run.status)
    run.started_at = _parse_datetime(data.get("started")) or run.started_at
    run.finished_at = _parse_datetime(data.get("finished")) or run.finished_at
    run.source_payload = data
    db.commit()
    return {"id": run.id, "job_id": run.source_job_id, "job_template_id": run.job_template_id, "status": run.status,
            "limit": run.limit, "extra_vars": run.extra_vars, "started_at": run.started_at, "finished_at": run.finished_at,
            "source_payload": run.source_payload}


@router.post("/jobs/{job_id}/cancel", response_model=AnsibleJobCancelResponse)
def cancel_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.get(AnsibleJobRun, job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ansible job run not found")
    try:
        data = _provider().cancel_job(run.source_job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    run.status = str(data.get("status") or "cancel_requested")
    run.source_payload = data
    db.commit()
    return {"id": run.id, "job_id": run.source_job_id, "status": run.status}
