"""API provider for BMC Helix CMDB."""

import time
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class CMDBAPIProvider:
    """Read configuration items from BMC Helix CMDB REST APIs."""

    DEFAULT_DATASET_ID = "BMC.SAMPLE"
    DEFAULT_NAMESPACE = "BMC.CORE"
    DEFAULT_SERVER_CLASS = "BMC_ComputerSystem"

    def __init__(
        self,
        *,
        dataset_id: str = DEFAULT_DATASET_ID,
        namespace: str = DEFAULT_NAMESPACE,
        server_class: str = DEFAULT_SERVER_CLASS,
    ) -> None:
        settings = get_settings()

        if not settings.cmdb_base_url:
            raise ValueError(
                "CMDB_BASE_URL is required when CMDB_PROVIDER=api"
            )

        if not settings.cmdb_username or not settings.cmdb_password:
            raise ValueError(
                "CMDB_USERNAME and CMDB_PASSWORD are required "
                "when CMDB_PROVIDER=api"
            )

        self.base_url = settings.cmdb_base_url.rstrip("/")
        self.timeout = settings.api_timeout_seconds
        self.max_retries = settings.api_max_retries
        self.verify_tls = settings.cmdb_verify_tls

        self.username = settings.cmdb_username
        self.password = settings.cmdb_password.get_secret_value()

        self.dataset_id = self._require_text(
            dataset_id,
            "dataset_id",
        )
        self.namespace = self._require_text(
            namespace,
            "namespace",
        )
        self.server_class = self._require_text(
            server_class,
            "server_class",
        )

        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            verify=self.verify_tls,
            headers={"Accept": "application/json"},
        )

        try:
            self._authenticate()
        except Exception:
            self.client.close()
            raise

    @staticmethod
    def _require_text(value: str, field_name: str) -> str:
        """Reject empty configuration values."""
        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} cannot be blank")

        return normalized

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
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()

        except httpx.HTTPError as exc:
            raise RuntimeError(
                "CMDB authentication failed. Check the base URL, "
                "credentials, network connectivity, and permissions."
            ) from exc

        token = response.text.strip().strip('"')

        if not token:
            raise RuntimeError(
                "CMDB authentication returned an empty token."
            )

        self.client.headers["Authorization"] = f"AR-JWT {token}"

    def close(self) -> None:
        """Release the HTTP connection pool."""
        self.client.close()

    def __enter__(self) -> "CMDBAPIProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a GET request with bounded retries."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.get(
                    path,
                    params=params,
                )

                if (
                    response.status_code in (429, 500, 502, 503, 504)
                    and attempt < self.max_retries
                ):
                    retry_after = response.headers.get("Retry-After")

                    try:
                        delay = float(retry_after) if retry_after else 0
                    except ValueError:
                        delay = 0

                    if delay <= 0:
                        delay = min(2**attempt, 10)

                    time.sleep(min(delay, 30))
                    continue

                response.raise_for_status()

                try:
                    data = response.json()
                except ValueError as exc:
                    raise RuntimeError(
                        "CMDB returned an invalid JSON response."
                    ) from exc

                if not isinstance(data, dict):
                    raise RuntimeError(
                        "CMDB response must be a JSON object."
                    )

                return data

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if status_code in (401, 403):
                    raise RuntimeError(
                        "CMDB authentication or permission failure "
                        f"(HTTP {status_code})."
                    ) from exc

                if status_code == 404:
                    raise RuntimeError(
                        f"CMDB resource was not found: {path}"
                    ) from exc

                if status_code == 429:
                    raise RuntimeError(
                        "CMDB rate limit reached after retries."
                    ) from exc

                raise RuntimeError(
                    f"CMDB API request failed with HTTP "
                    f"{status_code}: {path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc

                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue

                break

        raise RuntimeError(
            "CMDB request failed after "
            f"{self.max_retries + 1} attempts."
        ) from last_error

    @staticmethod
    def _normalize_attribute_key(value: str) -> str:
        """Normalize attribute names for case-insensitive matching."""
        return "".join(
            character.lower()
            for character in value
            if character.isalnum()
        )

    @classmethod
    def _attribute(
        cls,
        attributes: dict[str, Any],
        *candidate_names: str,
    ) -> Any:
        """Return the first matching attribute name or None."""
        normalized = {
            cls._normalize_attribute_key(str(key)): value
            for key, value in attributes.items()
        }

        for candidate in candidate_names:
            key = cls._normalize_attribute_key(candidate)

            if key in normalized:
                return normalized[key]

        return None

    @classmethod
    def _normalize_instance(
        cls,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        """Map common CMDB attributes to the simulator field names.

        The complete source object is retained in source_payload because
        client CMDB classes can expose different attribute sets.
        """
        attributes = item.get("attributes") or {}

        if not isinstance(attributes, dict):
            attributes = {}

        instance_id = item.get("instance_id")

        if instance_id is None:
            instance_id = item.get("id")

        return {
            "source_instance_id": (
                str(instance_id) if instance_id is not None else None
            ),
            "ci_name": cls._attribute(
                attributes,
                "Name",
                "InstanceName",
                "CIName",
            ),
            "dns_host_name": cls._attribute(
                attributes,
                "HostName",
                "DNSHostName",
                "Name",
            ),
            "ip_address": cls._attribute(
                attributes,
                "IPAddress",
                "IP_Address",
                "PrimaryIPAddress",
            ),
            "application_name": cls._attribute(
                attributes,
                "ApplicationName",
                "ITApplicationName",
            ),
            "asset_owner": cls._attribute(
                attributes,
                "AssetOwner",
                "OwnerName",
            ),
            "it_application_owner": cls._attribute(
                attributes,
                "ITApplicationOwner",
                "ApplicationOwner",
            ),
            "system_environment": cls._attribute(
                attributes,
                "SystemEnvironment",
                "Environment",
            ),
            "production_status": cls._attribute(
                attributes,
                "ProductionStatus",
            ),
            "os_type": cls._attribute(
                attributes,
                "OSType",
                "OperatingSystem",
                "OperatingSystemName",
            ),
            "os_version": cls._attribute(
                attributes,
                "OSVersion",
                "OperatingSystemVersion",
            ),
            "location": cls._attribute(
                attributes,
                "Site",
                "Location",
                "PhysicalLocation",
            ),
            "status": cls._attribute(
                attributes,
                "MarkAsDeleted",
                "Status",
                "AssetLifecycleStatus",
            ),
            "source_payload": item,
        }

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
        """Read a page of CMDB instances for the specified class."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        selected_class = self._require_text(
            class_name or self.server_class,
            "class_name",
        )
        selected_namespace = self._require_text(
            namespace or self.namespace,
            "namespace",
        )
        selected_dataset = self._require_text(
            dataset_id or self.dataset_id,
            "dataset_id",
        )

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
            clean_attributes = [
                attribute.strip()
                for attribute in attributes
                if attribute and attribute.strip()
            ]

            if clean_attributes:
                params["attributes"] = ",".join(clean_attributes)

        data = self._get(
            path,
            params=params,
        )

        instances = data.get("instances", [])

        if not isinstance(instances, list):
            raise RuntimeError(
                "CMDB response does not contain a valid 'instances' array."
            )

        return [
            self._normalize_instance(item)
            for item in instances
            if isinstance(item, dict)
        ]

    def get_server(
        self,
        instance_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a server CI by its external CMDB instance ID."""
        normalized_id = self._require_text(
            instance_id,
            "instance_id",
        )

        path = (
            "/api/cmdb/v1.0/instances/"
            f"{quote(self.dataset_id, safe='')}/"
            f"{quote(self.namespace, safe='')}/"
            f"{quote(self.server_class, safe='')}"
        )

        data = self._get(
            path,
            params={
                "ids": normalized_id,
                "dataset_mask": 0,
                "num_matches": "false",
            },
        )

        instances = data.get("instances", [])

        if not isinstance(instances, list):
            raise RuntimeError(
                "CMDB response does not contain a valid 'instances' array."
            )

        if not instances or not isinstance(instances[0], dict):
            return None

        return self._normalize_instance(instances[0])

    def list_servers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List server CIs and apply exact-match local filters."""
        records = self.list_instances(
            limit=limit,
            offset=offset,
        )

        if not filters:
            return records

        return [
            record
            for record in records
            if all(
                record.get(key) == value
                for key, value in filters.items()
            )
        ]