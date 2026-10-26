"""Database repositories for BMC Helix CMDB configuration items."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cmdb import (
    CMDBDatabase,
    CMDBMiddleware,
    CMDBServer,
)
from app.repositories.base import BaseRepository


class CMDBServerRepository(BaseRepository[CMDBServer]):
    """Database operations for server configuration items."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, CMDBServer)

    def get_by_source_id(
        self,
        source_instance_id: str,
    ) -> CMDBServer | None:
        """Find a server using its external CMDB instance ID."""
        statement = select(CMDBServer).where(
            CMDBServer.source_instance_id == source_instance_id
        )
        return self.db.scalars(statement).first()

    def get_by_ip(self, ip_address: str) -> list[CMDBServer]:
        """Return all servers matching an IP address.

        Return all matches so callers can detect ambiguous CIs.
        """
        statement = (
            select(CMDBServer)
            .where(CMDBServer.ip_address == ip_address)
            .order_by(CMDBServer.id)
        )
        return list(self.db.scalars(statement).all())

    def list_by_status(
        self,
        status: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CMDBServer]:
        """Return servers matching a CI status."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        statement = (
            select(CMDBServer)
            .where(CMDBServer.status == status)
            .order_by(CMDBServer.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class CMDBMiddlewareRepository(BaseRepository[CMDBMiddleware]):
    """Database operations for middleware configuration items."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, CMDBMiddleware)

    def get_by_source_id(
        self,
        source_instance_id: str,
    ) -> CMDBMiddleware | None:
        """Find middleware by its external CMDB instance ID."""
        statement = select(CMDBMiddleware).where(
            CMDBMiddleware.source_instance_id == source_instance_id
        )
        return self.db.scalars(statement).first()


class CMDBDatabaseRepository(BaseRepository[CMDBDatabase]):
    """Database operations for database configuration items."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, CMDBDatabase)

    def get_by_source_id(
        self,
        source_instance_id: str,
    ) -> CMDBDatabase | None:
        """Find a database CI by its external CMDB instance ID."""
        statement = select(CMDBDatabase).where(
            CMDBDatabase.source_instance_id == source_instance_id
        )
        return self.db.scalars(statement).first()