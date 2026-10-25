"""Business logic for BMC Helix CMDB configuration items."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories.cmdb import CMDBServerRepository
from app.schemas.cmdb import CMDBServerCreate, CMDBServerUpdate


class CMDBService:
    """Coordinate CMDB server operations and database persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CMDBServerRepository(db)

    def list_servers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """List persisted servers with optional filters."""
        query = self.db.query(self.repository.model)

        if status:
            query = query.filter(
                self.repository.model.status == status
            )

        if ip_address:
            query = query.filter(
                self.repository.model.ip_address == ip_address
            )

        total = query.count()
        items = (
            query.order_by(self.repository.model.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    def get_server(self, server_id: int) -> Any:
        """Retrieve a server by its database ID."""
        return self.repository.get_by_id(server_id)

    def find_servers_by_ip(self, ip_address: str) -> list[Any]:
        """Return all servers matching an IP address.

        Callers must handle missing and ambiguous matches explicitly.
        """
        return self.repository.get_by_ip(ip_address)

    def create_server(self, payload: CMDBServerCreate) -> Any:
        """Create a simulated server CI in PostgreSQL."""
        data = payload.model_dump()

        try:
            record = self.repository.create(data)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    def update_server(
        self,
        server_id: int,
        payload: CMDBServerUpdate,
    ) -> Any | None:
        """Update selected fields of a persisted server CI."""
        record = self.repository.get_by_id(server_id)
        if record is None:
            return None

        changes = payload.model_dump(exclude_unset=True)

        try:
            record = self.repository.update(record, changes)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise