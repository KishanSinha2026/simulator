
from typing import Any

from app.providers.json_provider import JsonProvider


class CMDBJsonProvider:
    """BMC Helix CMDB adapter backed by JSON fixtures."""

    def __init__(self) -> None:
        self.servers = JsonProvider("cmdb/servers.json")
        self.middleware = JsonProvider("cmdb/middleware.json")
        self.databases = JsonProvider("cmdb/databases.json")

    def get_server(self, instance_id: str) -> dict[str, Any] | None:
        return self.servers.get_by_id(instance_id)

    def list_servers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.servers.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def find_servers_by_ip(self, ip_address: str) -> list[dict[str, Any]]:
        """Return every matching server; do not silently choose ambiguous CIs."""
        return self.servers.list_records(
            limit=10000,
            filters={"ip_address": ip_address},
        )

    def list_middleware(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.middleware.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def list_databases(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.databases.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def update_server(
        self,
        instance_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a server fixture by its source identifier."""
        if not updates:
            raise ValueError("updates cannot be empty")

        records = self.servers._read_records()
        for record in records:
            record_id = record.get("id", record.get("source_id"))
            if str(record_id) == str(instance_id):
                record.update(updates)
                self.servers._write_records(records)
                return record

        raise ValueError(f"CMDB server {instance_id!r} was not found")
