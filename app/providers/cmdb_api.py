
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class CMDBAPIProvider:
    """BMC Helix CMDB REST API adapter."""

    def __init__(
        self,
        *,
        dataset_id: str = "BMC.SAMPLE",
        namespace: str = "BMC.CORE",
        server_class: str = "BMC_ComputerSystem",
    ) -> None:
        settings = get_settings()

        if not settings.cmdb_base_url:
            raise ValueError("CMDB_BASE_URL is required in API mode")

        if not settings.cmdb_username or not settings.cmdb_password:
            raise ValueError(
                "CMDB_USERNAME and CMDB_PASSWORD are required in API mode"
            )

        self.base_url = settings.cmdb_base_url.rstrip("/")
        self.timeout = settings.api_timeout_seconds
        self.max_retries = settings.api_max_retries
        self.verify_tls = settings.cmdb_verify_tls

        self.username = settings.cmdb_username
        self.password = settings.cmdb_password.get_secret_value()

        self.dataset_id = dataset_id
        self.namespace = namespace
        self.server_class = server_class

        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            verify=self.verify_tls,
            headers={"Accept": "application/json"},
        )

        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate using the AR System JWT login endpoint."""
        try:
            response = self.client.post(
                "/api/jwt/login",
                data={
                    "username": self.username,
                    "password": self.password,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self.client.close()
            raise RuntimeError(
                "CMDB authentication failed. Verify the base URL, "
                "credentials, and authentication configuration."
            ) from exc

        token = response.text.strip().strip('"')

        if not token:
            self.client.close()
            raise RuntimeError(
                "CMDB authentication returned an empty token."
            )

        self.client.headers["Authorization"] = f"AR-JWT {token}"

    def close(self) -> None:
        """Release HTTP resources."""
        self.client.close()

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.get(path, params=params)

                if (
                    response.status_code in (429, 500, 502, 503, 504)
                    and attempt < self.max_retries
                ):
                    continue

                response.raise_for_status()
                data = response.json()

                if not isinstance(data, dict):
                    raise ValueError("Unexpected CMDB response format")

                return data

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code

                if status in (401, 403):
                    raise RuntimeError(
                        f"CMDB authentication or permission failure "
                        f"(HTTP {status})."
                    ) from exc

                raise RuntimeError(
                    f"CMDB API request failed with HTTP {status}: {path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break

        raise RuntimeError(
            f"CMDB request failed after {self.max_retries + 1} attempts."
        ) from last_error

    def list_instances(
        self,
        *,
        class_name: str | None = None,
        namespace: str | None = None,
        dataset_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        attributes: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Read a page of CMDB instances for a specified class."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        selected_class = class_name or self.server_class
        selected_namespace = namespace or self.namespace
        selected_dataset = dataset_id or self.dataset_id

        path = (
            "/api/cmdb/v1.0/instances/"
            f"{quote(selected_dataset, safe='')}/"
            f"{quote(selected_namespace, safe='')}/"
            f"{quote(selected_class, safe='')}"
        )

        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
            "dataset_mask": 0,
            "num_matches": "false",
        }

        if attributes:
            params["attributes"] = ",".join(attributes)

        data = self._get(path, params=params)
        instances = data.get("instances", [])

        if not isinstance(instances, list):
            raise ValueError(
                "CMDB response does not contain a valid 'instances' array."
            )

        return [
            {
                "id": item.get("instance_id"),
                "instance_id": item.get("instance_id"),
                "class_name_key": item.get("class_name_key"),
                **(item.get("attributes") or {}),
                "source_payload": item,
            }
            for item in instances
            if isinstance(item, dict)
        ]

    def get_server(self, instance_id: str) -> dict[str, Any] | None:
        """Retrieve one server CI by its CMDB instance ID."""
        path = (
            "/api/cmdb/v1.0/instances/"
            f"{quote(self.dataset_id, safe='')}/"
            f"{quote(self.namespace, safe='')}/"
            f"{quote(self.server_class, safe='')}"
        )

        data = self._get(
            path,
            params={
                "ids": instance_id,
                "dataset_mask": 0,
                "num_matches": "false",
            },
        )

        instances = data.get("instances", [])

        if not isinstance(instances, list) or not instances:
            return None

        item = instances[0]
        if not isinstance(item, dict):
            return None

        return {
            "id": item.get("instance_id"),
            "instance_id": item.get("instance_id"),
            "class_name_key": item.get("class_name_key"),
            **(item.get("attributes") or {}),
            "source_payload": item,
        }

    def list_servers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List server CIs; apply requested filters to returned attributes."""
        records = self.list_instances(limit=limit, offset=offset)

        if not filters:
            return records

        return [
            record
            for record in records
            if all(record.get(key) == value for key, value in filters.items())
        ]
