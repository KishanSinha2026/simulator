"""Shared BRD patch eligibility checks."""

from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.squad1 import Squad1Vulnerability


def active_exception_targets(db: Session, targets: set[str]) -> set[str]:
    """Return normalized target identifiers covered by a current exception."""
    normalized = {target.strip().casefold() for target in targets if target and target.strip()}
    if not normalized:
        return set()
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Squad1Vulnerability.target)
        .filter(
            func.lower(func.trim(Squad1Vulnerability.target)).in_(normalized),
            Squad1Vulnerability.exception_id.isnot(None),
            Squad1Vulnerability.exception_id != "",
            or_(
                Squad1Vulnerability.exception_end_date.is_(None),
                Squad1Vulnerability.exception_end_date >= now,
            ),
        )
        .all()
    )
    return {str(row[0]).strip().casefold() for row in rows if row[0]}
