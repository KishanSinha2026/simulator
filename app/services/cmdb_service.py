"""Business logic for BMC Helix CMDB configuration items."""

from typing import Any

from sqlalchemy.orm import Session

from app.models.cmdb import (
    CMDBDatabase,
    CMDBMiddleware,
    CMDBRelationship,
    CMDBServer,
)
from app.providers.factory import get_provider
from app.repositories.cmdb import (
    CMDBDatabaseRepository,
    CMDBMiddlewareRepository,
    CMDBRelationshipRepository,
    CMDBServerRepository,
)
from app.schemas.cmdb import (
    CMDBDatabaseCreate,
    CMDBDatabaseUpdate,
    CMDBMiddlewareCreate,
    CMDBMiddlewareUpdate,
    CMDBRelationshipCreate,
    CMDBServerCreate,
    CMDBServerUpdate,
)


class CMDBService:
    """Coordinate CMDB server, middleware, database, and relationship operations."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CMDBServerRepository(db)
        self.middleware_repository = CMDBMiddlewareRepository(db)
        self.database_repository = CMDBDatabaseRepository(db)
        self.relationship_repository = CMDBRelationshipRepository(db)
        self.provider = get_provider("cmdb")

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        """Validate pagination parameters."""
        if not 1 <= limit <= 50000:
            raise ValueError("limit must be between 1 and 50000")

        if offset < 0:
            raise ValueError("offset cannot be negative")

    # ------------------------------------------------------------------
    # Server CI Operations (Database)
    # ------------------------------------------------------------------

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

        # Auto-import from active provider (API or JSON fixture) if database is empty
        if self.db.query(CMDBServer).count() == 0:
            self.import_provider_data()

        query = self.db.query(CMDBServer)

        if status:
            query = query.filter(CMDBServer.status == status)

        if ip_address:
            query = query.filter(CMDBServer.ip_address == ip_address.strip())

        total = query.count()

        items = (
            query.order_by(CMDBServer.id)
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

    def get_server(self, server_id: int) -> CMDBServer | None:
        """Retrieve a server CI by its internal database ID."""
        if server_id < 1:
            raise ValueError("server_id must be greater than zero")

        return self.repository.get_by_id(server_id)

    def find_servers_by_ip(
        self,
        ip_address: str,
    ) -> list[CMDBServer]:
        """Return all server CIs matching an IP address."""
        normalized_ip = ip_address.strip()

        if not normalized_ip:
            raise ValueError("ip_address cannot be blank")

        if self.db.query(CMDBServer).count() == 0:
            self.import_provider_data()

        return self.repository.get_by_ip(normalized_ip)

    def correlate_ip(self, ip_address: str) -> dict[str, Any]:
        """Correlate IP address to server CI following BRD Section 4.3 rules.

        Outcomes:
        - MATCHED: Exactly one active server CI found
        - CMDB_NOT_FOUND: No server CI found for this IP
        - AMBIGUOUS_MATCH: Multiple server CIs matched
        - CMDB_CI_INACTIVE: Server CI is inactive or deleted
        """
        servers = self.find_servers_by_ip(ip_address)

        if not servers:
            return {
                "ip_address": ip_address,
                "correlation_outcome": "CMDB_NOT_FOUND",
                "matched_servers": [],
                "message": "No server CI found in CMDB matching IP address.",
            }

        if len(servers) > 1:
            return {
                "ip_address": ip_address,
                "correlation_outcome": "AMBIGUOUS_MATCH",
                "matched_servers": servers,
                "message": f"Multiple ({len(servers)}) server CIs found for IP address. Held for review.",
            }

        server = servers[0]
        status_val = (server.status or "").strip().lower()
        if status_val in {"inactive", "deleted", "decommissioned", "retired"}:
            return {
                "ip_address": ip_address,
                "correlation_outcome": "CMDB_CI_INACTIVE",
                "matched_servers": servers,
                "message": f"Server CI {server.source_instance_id} is inactive ({server.status}). Held from automated execution.",
            }

        return {
            "ip_address": ip_address,
            "correlation_outcome": "MATCHED",
            "matched_servers": servers,
            "message": "Eligible server CI correlated successfully.",
        }

    def create_server(
        self,
        payload: CMDBServerCreate,
    ) -> CMDBServer:
        """Create a simulated CMDB server CI in PostgreSQL."""
        data = payload.model_dump()

        source_instance_id = data.get("source_instance_id")

        if not source_instance_id or not source_instance_id.strip():
            raise ValueError(
                "source_instance_id is required and cannot be blank"
            )

        data["source_instance_id"] = source_instance_id.strip()

        try:
            existing = self.repository.get_by_source_id(source_instance_id)
            if existing is not None:
                for k, v in data.items():
                    setattr(existing, k, v)
                self.db.commit()
                self.db.refresh(existing)
                return existing

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
    ) -> CMDBServer | None:
        """Update selected fields on an existing server CI."""
        if server_id < 1:
            raise ValueError("server_id must be greater than zero")

        record = self.repository.get_by_id(server_id)

        if record is None:
            return None

        changes = payload.model_dump(exclude_unset=True)

        if not changes:
            raise ValueError("At least one field must be supplied")

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

    # ------------------------------------------------------------------
    # Middleware CI Operations (Database)
    # ------------------------------------------------------------------

    def list_middleware(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        middleware_type: str | None = None,
    ) -> dict[str, Any]:
        """List persisted middleware CIs in PostgreSQL."""
        self._validate_pagination(limit, offset)

        query = self.db.query(CMDBMiddleware)

        if middleware_type:
            query = query.filter(CMDBMiddleware.middleware_type == middleware_type)

        total = query.count()
        items = (
            query.order_by(CMDBMiddleware.id)
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

    def get_middleware(self, middleware_id: int) -> CMDBMiddleware | None:
        """Retrieve middleware CI by internal ID."""
        return self.middleware_repository.get_by_id(middleware_id)

    def create_middleware(
        self,
        payload: CMDBMiddlewareCreate,
    ) -> CMDBMiddleware:
        """Create a middleware CI in PostgreSQL."""
        data = payload.model_dump()
        try:
            record = self.middleware_repository.create(data)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    def update_middleware(
        self,
        middleware_id: int,
        payload: CMDBMiddlewareUpdate,
    ) -> CMDBMiddleware | None:
        """Update selected fields on a middleware CI."""
        record = self.middleware_repository.get_by_id(middleware_id)
        if record is None:
            return None

        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("At least one field must be supplied")

        try:
            record = self.middleware_repository.update(record, changes)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Database CI Operations (Database)
    # ------------------------------------------------------------------

    def list_databases(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        database_type: str | None = None,
    ) -> dict[str, Any]:
        """List persisted database CIs in PostgreSQL."""
        self._validate_pagination(limit, offset)

        query = self.db.query(CMDBDatabase)

        if database_type:
            query = query.filter(CMDBDatabase.database_type == database_type)

        total = query.count()
        items = (
            query.order_by(CMDBDatabase.id)
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

    def get_database(self, database_id: int) -> CMDBDatabase | None:
        """Retrieve database CI by internal ID."""
        return self.database_repository.get_by_id(database_id)

    def create_database(
        self,
        payload: CMDBDatabaseCreate,
    ) -> CMDBDatabase:
        """Create a database CI in PostgreSQL."""
        data = payload.model_dump()
        try:
            record = self.database_repository.create(data)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    def update_database(
        self,
        database_id: int,
        payload: CMDBDatabaseUpdate,
    ) -> CMDBDatabase | None:
        """Update selected fields on a database CI."""
        record = self.database_repository.get_by_id(database_id)
        if record is None:
            return None

        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("At least one field must be supplied")

        try:
            record = self.database_repository.update(record, changes)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Relationship Operations (Database)
    # ------------------------------------------------------------------

    def list_relationships(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List relationships between CMDB CIs."""
        self._validate_pagination(limit, offset)

        query = self.db.query(CMDBRelationship)
        total = query.count()
        items = (
            query.order_by(CMDBRelationship.id)
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

    def get_relationship(self, relationship_id: int) -> CMDBRelationship | None:
        """Retrieve a relationship by internal ID."""
        return self.relationship_repository.get_by_id(relationship_id)

    def create_relationship(
        self,
        payload: CMDBRelationshipCreate,
    ) -> CMDBRelationship:
        """Create a relationship in PostgreSQL."""
        data = payload.model_dump()
        try:
            record = self.relationship_repository.create(data)
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Provider Operations (JSON Fixture or External CMDB API)
    # ------------------------------------------------------------------

    def list_provider_servers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List servers directly from the active provider (JSON/API)."""
        if hasattr(self.provider, "list_servers"):
            return self.provider.list_servers(limit=limit, offset=offset, filters=filters)
        return []

    def list_provider_middleware(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List middleware directly from the active provider."""
        if hasattr(self.provider, "list_middleware"):
            return self.provider.list_middleware(limit=limit, offset=offset, filters=filters)
        return []

    def list_provider_databases(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List databases directly from the active provider."""
        if hasattr(self.provider, "list_databases"):
            return self.provider.list_databases(limit=limit, offset=offset, filters=filters)
        return []

    def find_provider_servers_by_ip(self, ip_address: str) -> list[dict[str, Any]]:
        """Find servers by IP address in the active provider."""
        if hasattr(self.provider, "find_servers_by_ip"):
            return self.provider.find_servers_by_ip(ip_address)
        return []

    def create_provider_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a server CI in the active JSON provider."""
        if hasattr(self.provider, "create_server"):
            return self.provider.create_server(payload)
        raise ValueError("Active provider does not support creating servers")

    def import_provider_data(self) -> dict[str, Any]:
        """Import servers, middleware, and databases from the active provider into PostgreSQL."""
        servers_count = 0
        middleware_count = 0
        databases_count = 0
        errors = 0

        # 1. Import servers
        if hasattr(self.provider, "list_servers"):
            try:
                raw_servers = self.provider.list_servers(limit=50000)
                clean_servers: dict[str, dict[str, Any]] = {}
                for item in raw_servers:
                    sid = str(item.get("source_instance_id") or item.get("id") or "").strip()
                    if sid:
                        clean_servers[sid] = item

                chunk = list(clean_servers.values())
                chunk_size = 500
                for i in range(0, len(chunk), chunk_size):
                    batch = chunk[i : i + chunk_size]
                    batch_ids = [str(item.get("source_instance_id") or item.get("id")).strip() for item in batch]
                    existing_map = {
                        s.source_instance_id: s
                        for s in self.db.query(CMDBServer).filter(CMDBServer.source_instance_id.in_(batch_ids)).all()
                    }
                    for item in batch:
                        source_id = str(item.get("source_instance_id") or item.get("id")).strip()
                        existing = existing_map.get(source_id)
                        data = {
                            "source_instance_id": source_id,
                            "ci_name": item.get("ci_name"),
                            "dns_host_name": item.get("dns_host_name"),
                            "ip_address": item.get("ip_address"),
                            "application_name": item.get("application_name"),
                            "asset_owner": item.get("asset_owner"),
                            "it_application_owner": item.get("it_application_owner"),
                            "system_environment": item.get("system_environment"),
                            "production_status": item.get("production_status"),
                            "os_type": item.get("os_type"),
                            "os_version": item.get("os_version"),
                            "location": item.get("location"),
                            "status": item.get("status"),
                            "source_payload": item.get("source_payload") or item,
                        }
                        if existing is None:
                            self.db.add(CMDBServer(**data))
                        else:
                            for k, v in data.items():
                                setattr(existing, k, v)
                        servers_count += 1
                    self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        # 2. Import middleware
        if hasattr(self.provider, "list_middleware"):
            try:
                for item in self.provider.list_middleware(limit=5000):
                    source_id = str(item.get("source_instance_id") or item.get("id") or "").strip()
                    if not source_id:
                        continue
                    existing = self.middleware_repository.get_by_source_id(source_id)
                    data = {
                        "source_instance_id": source_id,
                        "ci_name": item.get("ci_name"),
                        "server_instance_id": item.get("server_instance_id"),
                        "hostname": item.get("hostname"),
                        "ip_address": item.get("ip_address"),
                        "location": item.get("location"),
                        "application_name": item.get("application_name"),
                        "asset_owner": item.get("asset_owner"),
                        "it_application_owner": item.get("it_application_owner"),
                        "middleware_type": item.get("middleware_type"),
                        "version": item.get("version"),
                        "status": item.get("status"),
                        "source_payload": item.get("source_payload") or item,
                    }
                    if existing is None:
                        self.db.add(CMDBMiddleware(**data))
                    else:
                        for k, v in data.items():
                            setattr(existing, k, v)
                    middleware_count += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        # 3. Import databases
        if hasattr(self.provider, "list_databases"):
            try:
                for item in self.provider.list_databases(limit=5000):
                    source_id = str(item.get("source_instance_id") or item.get("id") or "").strip()
                    if not source_id:
                        continue
                    existing = self.database_repository.get_by_source_id(source_id)
                    data = {
                        "source_instance_id": source_id,
                        "ci_name": item.get("ci_name"),
                        "server_instance_id": item.get("server_instance_id"),
                        "hostname": item.get("hostname"),
                        "ip_address": item.get("ip_address"),
                        "location": item.get("location"),
                        "asset_owner": item.get("asset_owner"),
                        "database_type": item.get("database_type"),
                        "version": item.get("version"),
                        "status": item.get("status"),
                        "source_payload": item.get("source_payload") or item,
                    }
                    if existing is None:
                        self.db.add(CMDBDatabase(**data))
                    else:
                        for k, v in data.items():
                            setattr(existing, k, v)
                    databases_count += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                errors += 1

        return {
            "servers_imported": servers_count,
            "middleware_imported": middleware_count,
            "databases_imported": databases_count,
            "errors": errors,
        }