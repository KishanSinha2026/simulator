"""Business logic for BMC Helix CMDB configuration items."""

from typing import Any

from sqlalchemy.orm import Session

from app.repositories.cmdb import CMDBServerRepository
from app.schemas.cmdb import CMDBServerCreate, CMDBServerUpdate


class CMDBService:
    """Coordinate CMDB server operations and PostgreSQL persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CMDBServerRepository(db)

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        """Validate pagination parameters."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        if offset < 0:
            raise ValueError("offset cannot be negative")

    def list_servers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """List persisted server CIs with optional filters."""
        self._validate_pagination(limit, offset)

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
            query
            .order_by(self.repository.model.id)
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

    def get_server(self, server_id: int) -> Any | None:
        """Retrieve a server CI by its internal database ID."""
        if server_id < 1:
            raise ValueError("server_id must be greater than zero")

        return self.repository.get_by_id(server_id)

    def find_servers_by_ip(
        self,
        ip_address: str,
    ) -> list[Any]:
        """Return all server CIs matching an IP address.

        Multiple matches are preserved so callers can detect ambiguous
        configuration items instead of selecting one arbitrarily.
        """
        normalized_ip = ip_address.strip()

        if not normalized_ip:
            raise ValueError("ip_address cannot be blank")

        return self.repository.get_by_ip(normalized_ip)

    def create_server(
        self,
        payload: CMDBServerCreate,
    ) -> Any:
        """Create a simulated CMDB server CI in PostgreSQL."""
        data = payload.model_dump()

        source_instance_id = data.get("source_instance_id")

        if not source_instance_id or not source_instance_id.strip():
            raise ValueError(
                "source_instance_id is required and cannot be blank"
            )

        data["source_instance_id"] = source_instance_id.strip()

        try:
            # Flush constraints before committing the transaction.
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
        """Update selected fields on an existing server CI."""
        if server_id < 1:
            raise ValueError("server_id must be greater than zero")

        record = self.repository.get_by_id(server_id)

        if record is None:
            return None

        changes = payload.model_dump(exclude_unset=True)

        if not changes:
            raise ValueError("At least one field must be supplied")

        # Prevent the source identity from being modified by a routine
        # update request. Source identity is managed separately.
        if "source_instance_id" in changes:
            raise ValueError(
                "source_instance_id cannot be changed through this endpoint"
            )

        if (
            "ci_name" in changes
            and changes["ci_name"] is not None
            and not changes["ci_name"].strip()
        ):
            raise ValueError("ci_name cannot be blank")

        if (
            "ip_address" in changes
            and changes["ip_address"] is not None
            and not changes["ip_address"].strip()
        ):
            raise ValueError("ip_address cannot be blank")

        try:
            record = self.repository.update(record, changes)

            self.db.commit()
            self.db.refresh(record)

            return record

        except Exception:
            self.db.rollback()
            raise