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


def _validate_pagination(limit: int, offset: int) -> None:
    """Validate common pagination parameters."""
    if limit < 1:
        raise ValueError("limit must be greater than zero")

    if offset < 0:
        raise ValueError("offset cannot be negative")


class SatelliteHostRepository(BaseRepository[SatelliteHost]):
    """Database operations for Satellite hosts."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SatelliteHost)

    def get_by_source_id(
        self,
        source_host_id: str,
    ) -> SatelliteHost | None:
        """Find a host by its external Satellite host ID."""
        statement = select(SatelliteHost).where(
            SatelliteHost.source_host_id == source_host_id
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

    def list_by_name(
        self,
        name: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SatelliteHost]:
        """Return hosts matching an exact name."""
        _validate_pagination(limit, offset)

        statement = (
            select(SatelliteHost)
            .where(SatelliteHost.name == name)
            .order_by(SatelliteHost.id)
            .limit(limit)
            .offset(offset)
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
        source_template_id: str,
    ) -> SatelliteJobTemplate | None:
        """Find a template by its external Satellite template ID."""
        statement = select(SatelliteJobTemplate).where(
            SatelliteJobTemplate.source_template_id == source_template_id
        )
        return self.db.scalars(statement).first()

    def list_by_name(
        self,
        name: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SatelliteJobTemplate]:
        """Return templates matching an exact name."""
        _validate_pagination(limit, offset)

        statement = (
            select(SatelliteJobTemplate)
            .where(SatelliteJobTemplate.name == name)
            .order_by(SatelliteJobTemplate.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class SatelliteJobRunRepository(BaseRepository[SatelliteJobRun]):
    """Database operations for Satellite job runs."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SatelliteJobRun)

    def get_by_source_id(
        self,
        source_invocation_id: str,
    ) -> SatelliteJobRun | None:
        """Find a job run by its external invocation ID."""
        statement = select(SatelliteJobRun).where(
            SatelliteJobRun.source_invocation_id == source_invocation_id
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
        _validate_pagination(limit, offset)

        statement = (
            select(SatelliteJobRun)
            .where(SatelliteJobRun.status == status)
            .order_by(SatelliteJobRun.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def list_by_template_id(
        self,
        template_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SatelliteJobRun]:
        """Return job runs associated with an internal template ID."""
        _validate_pagination(limit, offset)

        statement = (
            select(SatelliteJobRun)
            .where(SatelliteJobRun.template_id == template_id)
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
        job_run_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SatelliteJobHostResult]:
        """Return host results for an internal job-run database ID."""
        _validate_pagination(limit, offset)

        statement = (
            select(SatelliteJobHostResult)
            .where(SatelliteJobHostResult.job_run_id == job_run_id)
            .order_by(SatelliteJobHostResult.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def get_for_job_and_host(
        self,
        job_run_id: int,
        host_id: int,
    ) -> SatelliteJobHostResult | None:
        """Find the result for one host in one job run."""
        statement = select(SatelliteJobHostResult).where(
            SatelliteJobHostResult.job_run_id == job_run_id,
            SatelliteJobHostResult.host_id == host_id,
        )
        return self.db.scalars(statement).first()