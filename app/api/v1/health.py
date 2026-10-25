"""Health and readiness endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Application health check")
def health_check() -> dict[str, str]:
    """Confirm that the API process is responding."""
    return {
        "status": "healthy",
        "service": "vpm360-simulator",
    }


@router.get("/ready", summary="Application readiness check")
def readiness_check(db: Session = Depends(get_db)) -> dict[str, str]:
    """Confirm that the database is reachable."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="Database is not ready",
        ) from None

    return {
        "status": "ready",
        "database": "connected",
    }