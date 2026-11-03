"""Ansible Automation Platform job template and patch execution routes."""

from datetime import datetime
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ansible import AnsibleJobRun, AnsibleJobTemplate
from app.providers.factory import get_provider
from app.providers.ansible_fallback import AnsibleFallbackProvider
from app.providers.ansible_json import AnsibleJsonProvider
from app.schemas.connection import ConnectorConnectionResponse
from app.services.connection_service import check_connector_connection
from app.services.patching_guard import active_exception_targets
from app.schemas.ansible import (
    AnsibleJobCancelResponse,
    AnsibleJobLaunchResponse,
    AnsibleJobRunResponse,
    AnsibleJobRunListResponse,
    AnsibleJobTemplateListResponse,
    AnsibleLaunchRequest,
)

router = APIRouter(prefix="/ansible", tags=["Ansible Automation"])

def _provider():
    try:
        configured_provider = get_provider("ansible")
    except (ValueError, RuntimeError):
        return AnsibleJsonProvider()
    if isinstance(configured_provider, AnsibleJsonProvider):
        return configured_provider
    return AnsibleFallbackProvider(configured_provider, AnsibleJsonProvider())


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_extra_vars(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _job_response(run: AnsibleJobRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "job_id": run.source_job_id,
        "job_template_id": run.job_template_id,
        "status": run.status,
        "limit": run.limit,
        "extra_vars": run.extra_vars or {},
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "source_payload": run.source_payload,
    }


def _find_job_run(db: Session, job_id: str) -> AnsibleJobRun | None:
    """Accept either the controller's job ID or VPM360's local row ID."""
    run = db.query(AnsibleJobRun).filter_by(source_job_id=job_id).one_or_none()
    if run is not None:
        return run
    if job_id.isdecimal():
        return db.get(AnsibleJobRun, int(job_id))
    return None


@router.get("/job-templates", response_model=AnsibleJobTemplateListResponse)
def list_job_templates(
    limit: int = Query(100, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        data = _provider().list_templates(limit=limit, offset=offset)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    for item in data.get("results", []):
        source_id = str(item.get("id") or item.get("source_template_id") or "").strip()
        if not source_id:
            continue
        row = db.query(AnsibleJobTemplate).filter_by(source_template_id=source_id).one_or_none()
        values = {
            "source_template_id": source_id,
            "name": str(item.get("name") or source_id),
            "description": item.get("description"),
            "source_payload": item,
        }
        if row is None:
            db.add(AnsibleJobTemplate(**values))
        else:
            for key, value in values.items():
                setattr(row, key, value)
    db.commit()
    return {
        "items": data.get("results", []),
        "count": int(data.get("count") or 0),
        "next": data.get("next"),
        "provider_mode": data.get("provider_mode", "api"),
    }


def _import_templates(db: Session, *, limit: int, offset: int) -> dict[str, Any]:
    try:
        data = _provider().list_templates(limit=limit, offset=offset)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    imported = 0
    for item in data.get("results", []):
        source_id = str(item.get("id") or item.get("source_template_id") or "").strip()
        if not source_id:
            continue
        row = db.query(AnsibleJobTemplate).filter_by(source_template_id=source_id).one_or_none()
        values = {
            "source_template_id": source_id,
            "name": str(item.get("name") or source_id),
            "description": item.get("description"),
            "source_payload": item,
        }
        if row is None:
            db.add(AnsibleJobTemplate(**values))
        else:
            for key, value in values.items():
                setattr(row, key, value)
        imported += 1
    db.commit()
    return {"status": "completed", "templates_imported": imported, "count": data.get("count", 0), "limit": limit, "offset": offset}


@router.post("/import")
def import_job_templates(
    limit: int = Query(50000, ge=1, le=50000, description="Maximum templates to import"),
    offset: int = Query(0, ge=0, description="Number of templates to skip"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Import a page of AAP templates into PostgreSQL, retaining the source JSON."""
    return _import_templates(db, limit=limit, offset=offset)


@router.get("/connection", response_model=ConnectorConnectionResponse)
def test_connection(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Check controller connectivity without masking API failure as fixture mode."""
    return check_connector_connection("ansible", db)


@router.get("/jobs", response_model=AnsibleJobRunListResponse)
def list_jobs(
    limit: int = Query(100, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Fetch recent controller jobs and upsert their status into PostgreSQL."""
    try:
        data = _provider().list_jobs(limit=limit, offset=offset)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    for item in data.get("results", []):
        source_id = str(item.get("id") or "").strip()
        if not source_id:
            continue
        template_id = item.get("job_template") or item.get("unified_job_template") or "unknown"
        run = db.query(AnsibleJobRun).filter_by(source_job_id=source_id).one_or_none()
        values = {
            "source_job_id": source_id,
            "job_template_id": str(template_id),
            "status": str(item.get("status") or "unknown"),
            "limit": item.get("limit") or None,
            "extra_vars": _parse_extra_vars(item.get("extra_vars")),
            "started_at": _parse_datetime(item.get("started")),
            "finished_at": _parse_datetime(item.get("finished")),
            "source_payload": item,
        }
        if run is None:
            db.add(AnsibleJobRun(**values))
        else:
            for key, value in values.items():
                setattr(run, key, value)
    db.commit()

    source_ids = [str(item.get("id")) for item in data.get("results", []) if item.get("id") is not None]
    records = (
        db.query(AnsibleJobRun)
        .filter(AnsibleJobRun.source_job_id.in_(source_ids))
        .all()
        if source_ids else []
    )
    by_source_id = {record.source_job_id: record for record in records}
    return {
        "items": [
            _job_response(by_source_id[str(item["id"])])
            for item in data.get("results", [])
            if str(item.get("id")) in by_source_id
        ],
        "count": int(data.get("count") or 0),
        "next": data.get("next"),
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
    return {
        "id": run.id,
        "job_id": run.source_job_id,
        "status": run.status,
        "job_template_id": run.job_template_id,
        "simulated": bool((run.source_payload or {}).get("is_simulated")),
    }


@router.get("/jobs/{job_id}", response_model=AnsibleJobRunResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = _find_job_run(db, job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ansible job run not found")
    if (run.source_payload or {}).get("is_simulated"):
        data = run.source_payload
    else:
        try:
            data = _provider().get_job(run.source_job_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    run.status = str(data.get("status") or run.status)
    run.started_at = _parse_datetime(data.get("started")) or run.started_at
    run.finished_at = _parse_datetime(data.get("finished")) or run.finished_at
    run.source_payload = data
    db.commit()
    return _job_response(run)


@router.post("/jobs/{job_id}/cancel", response_model=AnsibleJobCancelResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = _find_job_run(db, job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ansible job run not found")
    if (run.source_payload or {}).get("is_simulated"):
        data = AnsibleJsonProvider().cancel_job(run.source_job_id)
    else:
        try:
            data = _provider().cancel_job(run.source_job_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    run.status = str(data.get("status") or "cancel_requested")
    run.source_payload = data
    db.commit()
    return {"id": run.id, "job_id": run.source_job_id, "status": run.status}
