"""JSON fixture provider for BMC Helix CMDB simulation."""

from typing import Any

from app.providers.json_provider import JsonProvider


class CMDBJsonProvider:
    """Read and update simulated CMDB configuration items."""

    SERVER_UPDATE_FIELDS = {
        "ci_name",
        "dns_host_name",
        "ip_address",
        "application_name",
        "asset_owner",
        "it_application_owner",
        "system_environment",
        "production_status",
        "os_type",
        "os_version",
        "location",
        "status",
        "last_patch_updated_at",
        "source_payload",
    }

    def __init__(self) -> None:
        self.servers = JsonProvider("cmdb/servers.json")
        self.middleware = JsonProvider("cmdb/middleware.json")
        self.databases = JsonProvider("cmdb/databases.json")

    @staticmethod
    def _get_by_source_id(
        provider: JsonProvider,
        source_instance_id: str,
    ) -> dict[str, Any] | None:
        """Find a record by simulator ID or source instance ID."""
        record = provider.get_by_id(source_instance_id)

        if record is not None:
            return record

        matches = provider.list_records(
            limit=10000,
            filters={"source_instance_id": source_instance_id},
        )

        return matches[0] if matches else None

    def get_server(
        self,
        instance_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a server CI by simulator or external instance ID."""
        return self._get_by_source_id(self.servers, instance_id)

    def list_servers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List server CIs with optional filters and pagination."""
        return self.servers.list_records(
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def find_servers_by_ip(
        self,
        ip_address: str,
    ) -> list[dict[str, Any]]:
        """Return every server matching an IP address."""
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
        """List middleware CIs with optional filters."""
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
        """List database CIs with optional filters."""
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
        """Update an existing simulated server CI."""
        if not updates:
            raise ValueError("Updates cannot be empty")

        unsupported_fields = set(updates) - self.SERVER_UPDATE_FIELDS

        if unsupported_fields:
            raise ValueError(
                "Unsupported CMDB server update fields: "
                + ", ".join(sorted(unsupported_fields))
            )

        records = self.servers._read_records()

        for record in records:
            record_id = str(record.get("id", ""))
            source_id = str(record.get("source_instance_id", ""))

            if instance_id not in (record_id, source_id):
                continue

            updated_record = dict(record)
            updated_record.update(updates)

            # Preserve the simulator ID and source identity.
            updated_record["id"] = record.get("id")
            updated_record["source_instance_id"] = source_id

            record.update(updates)
            self.servers._write_records(records)

            return updated_record

        raise ValueError(
            f"CMDB server {instance_id!r} was not found"
        )