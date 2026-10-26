
"""API provider for BMC Helix CMDB."""

import json
import time
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class CMDBAPIProvider:
    """Read and selectively update BMC Helix CMDB configuration items."""

    DEFAULT_NAMESPACE = "BMC.CORE"
    DEFAULT_SERVER_CLASS = "BMC_ComputerSystem"
    IP_ENDPOINT_CLASS = "BMC_IPEndpoint"

    def __init__(
        self,
        *,
        dataset_id: str | None = None,
        namespace: str = DEFAULT_NAMESPACE,
        server_class: str = DEFAULT_SERVER_CLASS,
        relationship_class: str | None = None,
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

        # Do not silently use BMC.SAMPLE in a client environment.
        configured_dataset = (
            dataset_id
            or getattr(settings, "cmdb_dataset_id", None)
        )
        self.dataset_id = self._require_text(
            configured_dataset,
            "CMDB_DATASET_ID",
        )

        self.namespace = self._require_text(
            namespace,
            "namespace",
        )
        self.server_class = self._require_text(
            server_class,
            "server_class",
        )

        self.relationship_class = (
            relationship_class
            or getattr(settings, "cmdb_relationship_class", "")
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
    def _require_text(
        value: str | None,
        field_name: str,
    ) -> str:
        """Reject missing or empty configuration values."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be configured")

        return value.strip()

    @staticmethod
    def _require_ip_text(value: str) -> str:
        """Validate that the supplied IP search value is non-empty."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("ip_address cannot be blank")
        return value.strip()

    def _authenticate(self) -> None:
        """Authenticate through the BMC AR System JWT login endpoint."""
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
                response = self.client.get(path, params=params)

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

    def _patch(
        self,
        path: str,
        *,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform a PATCH request with bounded retries."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.patch(
                    path,
                    json=payload,
                    headers={"Content-Type": "application/json"},
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

                # Some successful PATCH responses have no response body.
                if not response.content:
                    return {"status_code": response.status_code}

                try:
                    data = response.json()
                except ValueError:
                    return {
                        "status_code": response.status_code,
                        "response_text": response.text,
                    }

                if not isinstance(data, dict):
                    return {
                        "status_code": response.status_code,
                        "response": data,
                    }

                return {
                    "status_code": response.status_code,
                    "response": data,
                }

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if status_code in (401, 403):
                    raise RuntimeError(
                        "CMDB writeback authentication or permission "
                        f"failure (HTTP {status_code})."
                    ) from exc

                if status_code == 404:
                    raise RuntimeError(
                        f"CMDB writeback resource was not found: {path}"
                    ) from exc

                if status_code == 429:
                    raise RuntimeError(
                        "CMDB writeback rate limit reached after retries."
                    ) from exc

                raise RuntimeError(
                    f"CMDB PATCH failed with HTTP {status_code}: {path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc

                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue
                break

        raise RuntimeError(
            "CMDB PATCH failed after "
            f"{self.max_retries + 1} attempts."
        ) from last_error

    @staticmethod
    def _extract_instances(
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract instances only from a recognized instances response."""
        instances = data.get("instances", [])

        if not isinstance(instances, list):
            raise RuntimeError(
                "CMDB response does not contain a valid 'instances' array."
            )

        return [
            item for item in instances
            if isinstance(item, dict)
        ]

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
        """Return the first matching attribute or None."""
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
        """Map CMDB fields while retaining the full original object."""
        attributes = item.get("attributes") or {}

        if not isinstance(attributes, dict):
            attributes = {}

        instance_id = (
            item.get("instance_id")
            or item.get("instanceId")
            or item.get("InstanceId")
            or item.get("id")
        )

        return {
            "source_instance_id": (
                str(instance_id) if instance_id is not None else None
            ),
            "ci_name": cls._attribute(
                attributes, "Name", "InstanceName", "CIName"
            ),
            "dns_host_name": cls._attribute(
                attributes, "HostName", "DNSHostName"
            ),
            "ip_address": cls._attribute(
                attributes,
                "Address",
                "IPAddress",
                "IP_Address",
                "PrimaryIPAddress",
            ),
            "application_name": cls._attribute(
                attributes, "ApplicationName", "ITApplicationName"
            ),
            "asset_owner": cls._attribute(
                attributes, "AssetOwner", "OwnerName"
            ),
            "it_application_owner": cls._attribute(
                attributes, "ITApplicationOwner", "ApplicationOwner"
            ),
            "system_environment": cls._attribute(
                attributes, "SystemEnvironment", "Environment"
            ),
            "production_status": cls._attribute(
                attributes, "ProductionStatus"
            ),
            "os_type": cls._attribute(
                attributes, "OSType", "OperatingSystem",
                "OperatingSystemName",
            ),
            "os_version": cls._attribute(
                attributes, "OSVersion", "OperatingSystemVersion"
            ),
            "location": cls._attribute(
                attributes, "Site", "Location", "PhysicalLocation"
            ),
            "status": cls._attribute(
                attributes,
                "MarkAsDeleted",
                "Status",
                "AssetLifecycleStatus",
            ),
            "source_payload": item,
        }

    def find_ip_endpoints(
        self,
        ip_address: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Find BMC_IPEndpoint records by their Address attribute.

        This follows the BRD's IP-only primary correlation rule.
        It deliberately does not fall back to hostname matching.
        """
        source_ip = self._require_ip_text(ip_address)

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        path = (
            "/api/cmdb/v1.0/instances/"
            f"{quote(self.dataset_id, safe='')}/"
            f"{quote(self.namespace, safe='')}/"
            f"{quote(self.IP_ENDPOINT_CLASS, safe='')}"
        )

        # Qualification follows the request shape documented in the BRD.
        data = self._get(
            path,
            params={
                "qualification": f"'Address'=\"{source_ip}\"",
                "attributes": "InstanceId,Name,Address,SystemName",
                "offset": offset,
                "limit": limit,
                "dataset_mask": 0,
                "num_matches": "false",
            },
        )

        return [
            self._normalize_instance(item)
            for item in self._extract_instances(data)
        ]

    def walk_relationships(
        self,
        endpoint_instance_id: str,
        *,
        relationship_class: str | None = None,
        limit: int = 100,
        levels: int = 2,
    ) -> dict[str, Any]:
        """Traverse CMDB relationships starting from an IP endpoint.

        The relationship class and traversal direction must be approved
        by the client's CMDB team before the live integration is enabled.
        The raw graphwalk response is returned for contract-specific
        interpretation; no undocumented response shape is assumed here.
        """
        start_id = self._require_text(
            endpoint_instance_id,
            "endpoint_instance_id",
        )
        relation_class = self._require_text(
            relationship_class or self.relationship_class,
            "CMDB_RELATIONSHIP_CLASS",
        )

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if not 1 <= levels <= 10:
            raise ValueError("levels must be between 1 and 10")

        query = {
            "limit": limit,
            "num_levels_to_traverse": levels,
            "dataset_id": self.dataset_id,
            "start_node": {
                "class_name_key": {
                    "namespace": self.namespace,
                    "name": self.IP_ENDPOINT_CLASS,
                },
                "instance_id": start_id,
            },
            "relationship_selectors_filters": [
                {
                    "class_name_key": {
                        "namespace": self.namespace,
                        "name": relation_class,
                    },
                    "direction_to_walk": "BOTH",
                }
            ],
        }

        return self._get(
            "/api/cmdb/v1.0/graphwalk",
            params={
                "graph_walk_query": json.dumps(
                    query,
                    separators=(",", ":"),
                )
            },
        )

    def get_server(
        self,
        instance_id: str,
        *,
        dataset_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Read a ComputerSystem CI using its exact source instance ID."""
        normalized_id = self._require_text(
            instance_id,
            "instance_id",
        )
        selected_dataset = self._require_text(
            dataset_id or self.dataset_id,
            "dataset_id",
        )

        path = (
            "/api/cmdb/v1.0/instances/"
            f"{quote(selected_dataset, safe='')}/"
            f"{quote(self.namespace, safe='')}/"
            f"{quote(self.server_class, safe='')}/"
            f"{quote(normalized_id, safe='')}"
        )

        data = self._get(path)
        instances = self._extract_instances(data)

        if instances:
            matching = [
                item for item in instances
                if str(
                    item.get("instance_id")
                    or item.get("instanceId")
                    or item.get("InstanceId")
                    or item.get("id")
                    or ""
                ) == normalized_id
            ]

            if len(matching) == 1:
                return self._normalize_instance(matching[0])

            if len(instances) == 1 and not matching:
                # Retain the path's source identity if the response omits it.
                record = self._normalize_instance(instances[0])
                if not record.get("source_instance_id"):
                    record["source_instance_id"] = normalized_id
                return record

            if len(matching) > 1:
                raise RuntimeError(
                    "CMDB returned duplicate records for one server "
                    "instance ID; hold for review."
                )

            return None

        # Some CMDB installations return the CI directly rather than
        # wrapping it in an 'instances' array. Accept only objects that
        # visibly contain an attributes object.
        if isinstance(data.get("attributes"), dict):
            record = self._normalize_instance(data)
            if not record.get("source_instance_id"):
                record["source_instance_id"] = normalized_id
            return record

        return None

    def get_attribute_metadata(
        self,
        *,
        class_name: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve attribute metadata for a CMDB class."""
        selected_class = self._require_text(
            class_name or self.server_class,
            "class_name",
        )
        selected_namespace = self._require_text(
            namespace or self.namespace,
            "namespace",
        )

        path = (
            "/api/cmdb/v1.0/attributes/"
            f"{quote(selected_namespace, safe='')}/"
            f"{quote(selected_class, safe='')}"
        )

        return self._get(path)

    def write_patch_metadata(
        self,
        instance_id: str,
        *,
        os_version: str,
        last_patch_updated_at: str,
    ) -> dict[str, Any]:
        """Write the two approved patch fields to a server CI.

        Writeback stays disabled unless CMDB_WRITEBACK_ENABLED=true
        and the client confirms the dataset, class and exact attribute
        names. This method intentionally does not infer these names.
        """
        settings = get_settings()

        if not getattr(settings, "cmdb_writeback_enabled", False):
            raise RuntimeError(
                "CMDB writeback is disabled. Enable it only after "
                "IndusInd approves the writeback timing and mapping."
            )

        write_dataset = self._require_text(
            getattr(settings, "cmdb_writeback_dataset_id", None),
            "CMDB_WRITEBACK_DATASET_ID",
        )
        write_namespace = self._require_text(
            getattr(settings, "cmdb_writeback_namespace", None),
            "CMDB_WRITEBACK_NAMESPACE",
        )
        write_class = self._require_text(
            getattr(settings, "cmdb_writeback_class_name", None),
            "CMDB_WRITEBACK_CLASS_NAME",
        )
        os_attribute = self._require_text(
            getattr(settings, "cmdb_os_version_attribute", None),
            "CMDB_OS_VERSION_ATTRIBUTE",
        )
        timestamp_attribute = self._require_text(
            getattr(settings, "cmdb_last_patch_attribute", None),
            "CMDB_LAST_PATCH_ATTRIBUTE",
        )

        if os_attribute == timestamp_attribute:
            raise ValueError(
                "OS version and last-patch attributes must be different."
            )

        if not isinstance(os_version, str) or not os_version.strip():
            raise ValueError("os_version cannot be blank")
        if (
            not isinstance(last_patch_updated_at, str)
            or not last_patch_updated_at.strip()
        ):
            raise ValueError("last_patch_updated_at cannot be blank")

        source_id = self._require_text(instance_id, "instance_id")

        path = (
            "/api/cmdb/v1.0/instances/"
            f"{quote(write_dataset, safe='')}/"
            f"{quote(write_namespace, safe='')}/"
            f"{quote(write_class, safe='')}/"
            f"{quote(source_id, safe='')}"
        )

        payload = {
            "attributes": {
                os_attribute: os_version.strip(),
                timestamp_attribute: last_patch_updated_at.strip(),
            }
        }

        return self._patch(path, payload=payload)

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
        """Read one page of CMDB instances for a specified class."""
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

        data = self._get(path, params=params)

        return [
            self._normalize_instance(item)
            for item in self._extract_instances(data)
        ]

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
