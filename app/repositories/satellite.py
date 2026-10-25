"""Database repositories for Red Hat Satellite resources."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.satellite import (
    SatelliteHost,
    SatelliteJobHostResult,
    SatelliteJobRun,
    SatelliteJobTemplate,
)
from app.repositories.base import BaseRepository


class SatelliteHostRepository(BaseRepository[SatelliteHost]):
    """Database operations for Satellite hosts."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SatelliteHost)

    def get_by_source_id(self, source_id: str) -> SatelliteHost | None:
        """Find a host by its external Satellite identifier."""
        statement = select(SatelliteHost).where(
            SatelliteHost.source_id == source_id
        )
        return self.db.scalars(statement).first()

    def get_by_ip(self, ip_address: str) -> list[SatelliteHost]:
        """Return every host matching an IP address."""
        statement = (
            select(SatelliteHost)
            .where(SatelliteHost.ip_address == ip_address)
            .order_by(SatelliteHost.id)
        )
        return list(self.db.scalars(statement).all())


class SatelliteJobTemplateRepository(
    BaseRepository[SatelliteJobTemplate]
):
    """Database operations for Satellite job templates."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SatelliteJobTemplate)

    def get_by_source_id(
        self,
        source_id: str,
    ) -> SatelliteJobTemplate | None:
        """Find a job template by its external identifier."""
        statement = select(SatelliteJobTemplate).where(
            SatelliteJobTemplate.source_id == source_id
        )
        return self.db.scalars(statement).first()


class SatelliteJobRunRepository(BaseRepository[SatelliteJobRun]):
    """Database operations for Satellite job runs."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SatelliteJobRun)

    def get_by_source_id(self, source_id: str) -> SatelliteJobRun | None:
        """Find a job run by its external identifier."""
        statement = select(SatelliteJobRun).where(
            SatelliteJobRun.source_id == source_id
        )
        return self.db.scalars(statement).first()

    def list_by_status(
        self,
        status: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SatelliteJobRun]:
        """Return job runs matching a status."""
        statement = (
            select(SatelliteJobRun)
            .where(SatelliteJobRun.status == status)
            .order_by(SatelliteJobRun.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class SatelliteJobHostResultRepository(
    BaseRepository[SatelliteJobHostResult]
):
    """Database operations for per-host job results."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SatelliteJobHostResult)

    def list_by_job_run_id(
        self,
        job_run_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SatelliteJobHostResult]:
        """Return host results for an external job-run identifier."""
        statement = (
            select(SatelliteJobHostResult)
            .where(SatelliteJobHostResult.job_run_id == job_run_id)
            .order_by(SatelliteJobHostResult.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())