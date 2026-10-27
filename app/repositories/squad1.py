"""Database repository for Squad1 vulnerability records."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.squad1 import Squad1Vulnerability
from app.repositories.base import BaseRepository


class Squad1Repository(BaseRepository[Squad1Vulnerability]):
    """Database operations specific to Squad1 vulnerabilities."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Squad1Vulnerability)

    def get_by_vulnerability_no(
        self,
        vulnerability_no: str,
    ) -> Squad1Vulnerability | None:
        """Find a vulnerability by its unique Squad1 vulnerability number."""
        statement = select(Squad1Vulnerability).where(
            Squad1Vulnerability.vulnerability_no == vulnerability_no.strip()
        )
        return self.db.scalars(statement).first()

    def list_exceptions(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Squad1Vulnerability]:
        """Return vulnerabilities with active approved exceptions per BRD Section 4.2."""
        statement = (
            select(Squad1Vulnerability)
            .where(Squad1Vulnerability.exception_id.isnot(None))
            .order_by(Squad1Vulnerability.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())
