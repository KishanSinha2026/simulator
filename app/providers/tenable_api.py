
from typing import Any

import httpx

from app.core.config import get_settings


class TenableAPIProvider:
    """Read vulnerability data from Tenable Vulnerability Management."""

    def __init__(self) -> None:
        settings = get_settings()

        self.base_url = (
            settings.tenable_base_url or "https://cloud.tenable.com"
        ).rstrip("/")
        self.timeout = settings.api_timeout_seconds
        self.max_retries = settings.api_max_retries
        self.verify_tls = settings.tenable_verify_tls

        access_key = (
            settings.tenable_access_key.get_secret_value()
            if settings.tenable_access_key
            else ""
        )
        secret_key = (
            settings.tenable_secret_key.get_secret_value()
            if settings.tenable_secret_key
            else ""
        )

        if not access_key or not secret_key:
            raise ValueError(
                "Tenable API mode requires TENABLE_ACCESS_KEY and "
                "TENABLE_SECRET_KEY in the environment."
            )

        self.headers = {
            "Accept": "application/json",
            "X-ApiKeys": (
                f"accessKey={access_key}; secretKey={secret_key}"
            ),
        }

        self.client = httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            verify=self.verify_tls,
        )

    def close(self) -> None:
        """Release the HTTP connection pool."""
        self.client.close()

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.get(path, params=params)

                if (
                    response.status_code == 429
                    or response.status_code >= 500
                ) and attempt < self.max_retries:
                    continue

                response.raise_for_status()

                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError(
                        f"Unexpected JSON response from Tenable: {path}"
                    )

                return data

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code

                if status in (401, 403):
                    raise RuntimeError(
                        f"Tenable authentication or permission failure "
                        f"(HTTP {status}). Check the API keys and account "
                        "permissions."
                    ) from exc

                if status == 429:
                    raise RuntimeError(
                        "Tenable rate limit reached. Retry the request later."
                    ) from exc

                raise RuntimeError(
                    f"Tenable API request failed with HTTP {status}: {path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break

        raise RuntimeError(
            f"Could not connect to Tenable after "
            f"{self.max_retries + 1} attempts."
        ) from last_error

    def list_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve and locally paginate Tenable vulnerability records."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        params: dict[str, Any] = {}
        query_filters = filters or {}

        if "date_range" in query_filters:
            params["date_range"] = int(query_filters["date_range"])

        if "severity" in query_filters:
            params["filter.0.filter"] = "severity"
            params["filter.0.quality"] = "eq"
            params["filter.0.value"] = str(
                query_filters["severity"]
            )

        data = self._get(
            "/workbenches/vulnerabilities",
            params=params,
        )

        vulnerabilities = data.get("vulnerabilities", [])

        if not isinstance(vulnerabilities, list):
            raise ValueError(
                "Tenable response does not contain a valid "
                "'vulnerabilities' array."
            )

        normalized = [
            self._normalize_finding(item)
            for item in vulnerabilities
            if isinstance(item, dict)
        ]

        return normalized[offset : offset + limit]

    def get_finding(
        self,
        plugin_id: str | int,
    ) -> dict[str, Any] | None:
        """Retrieve plugin details by plugin ID."""
        data = self._get(
            f"/workbenches/vulnerabilities/{int(plugin_id)}/info"
        )

        info = data.get("info")

        if not isinstance(info, dict):
            return None

        return self._normalize_finding(info)

    @staticmethod
    def _normalize_finding(
        item: dict[str, Any],
    ) -> dict[str, Any]:
        """Map available Tenable fields to the simulator's field names."""
        return {
            "id": str(item.get("plugin_id", "")),
            "plugin_id": item.get("plugin_id"),
            "plugin_name": item.get("plugin_name"),
            "severity": item.get("severity"),
            "synopsis": item.get("synopsis"),
            "description": item.get("description"),
            "cvss_v3_base_score": item.get("cvss3_base_score"),
            "cvss_v4_base_score": item.get("cvss4_base_score"),
            "count": item.get("count"),
            "plugin_family": item.get("plugin_family"),
            "vulnerability_state": item.get("vulnerability_state"),
            "source_payload": item,
        }
