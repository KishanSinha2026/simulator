"""API provider for Tenable Vulnerability Management.

The current API route uses Tenable's Workbench Vulnerabilities endpoint.
That endpoint is not assumed to return the complete per-host 54-field export
shown in VPM360 BRD Appendix A. `normalize_tenable_record` maps available
fields and records the missing BRD fields for inspection.
"""

import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.providers.tenable_normalizer import normalize_tenable_record


class TenableAPIProvider:
    """Read vulnerability information from Tenable Vulnerability Management."""

    DEFAULT_BASE_URL = "https://cloud.tenable.com"
    MAX_WORKBENCH_RESULTS = 5000

    def __init__(self) -> None:
        settings = get_settings()

        self.base_url = (
            settings.tenable_base_url or self.DEFAULT_BASE_URL
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
                "TENABLE_SECRET_KEY to be configured."
            )

        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Accept": "application/json",
                "X-ApiKeys": (
                    f"accessKey={access_key}; secretKey={secret_key}"
                ),
            },
            timeout=self.timeout,
            verify=self.verify_tls,
        )

    def close(self) -> None:
        """Release the HTTP connection pool."""
        self.client.close()

    def __enter__(self) -> "TenableAPIProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a GET request with bounded retries."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.get(path, params=params)

                if (
                    response.status_code == 429
                    or response.status_code >= 500
                ):
                    if attempt < self.max_retries:
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
                        "Tenable returned an invalid JSON response."
                    ) from exc

                if not isinstance(data, dict):
                    raise RuntimeError(
                        f"Unexpected JSON response from Tenable: {path}"
                    )

                return data

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if status_code in (401, 403):
                    raise RuntimeError(
                        "Tenable authentication or permission failure "
                        f"(HTTP {status_code}). Check the API keys and "
                        "account permissions."
                    ) from exc

                if status_code == 429:
                    raise RuntimeError(
                        "Tenable rate limit reached after retries."
                    ) from exc

                raise RuntimeError(
                    "Tenable API request failed with HTTP "
                    f"{status_code}: {path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc

                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue

                break

        raise RuntimeError(
            "Could not connect to Tenable after "
            f"{self.max_retries + 1} attempts."
        ) from last_error

    def list_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List Tenable Workbench vulnerability summaries.

        This endpoint returns a plugin-level Workbench representation; it is
        not assumed to be the complete per-host 54-field scanner export. The
        endpoint is limited to 5,000 results. Pagination/contract must be
        validated against the client's actual Tenable deployment.
        """
        if not 1 <= limit <= self.MAX_WORKBENCH_RESULTS:
            raise ValueError("limit must be between 1 and 5000")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        if offset >= self.MAX_WORKBENCH_RESULTS:
            raise ValueError(
                "The Workbench endpoint returns at most 5000 results. "
                "Use a confirmed export API for larger datasets."
            )

        query_filters = filters or {}
        params: dict[str, Any] = {}

        if "date_range" in query_filters:
            try:
                date_range = int(query_filters["date_range"])
            except (TypeError, ValueError) as exc:
                raise ValueError("date_range must be an integer") from exc

            if date_range < 1:
                raise ValueError("date_range must be positive")

            params["date_range"] = date_range

        if "severity" in query_filters:
            severity = str(query_filters["severity"]).strip().lower()

            if severity not in {
                "info",
                "informational",
                "low",
                "medium",
                "high",
                "critical",
            }:
                raise ValueError(
                    "severity must be informational, info, low, medium, "
                    "high, or critical"
                )

            params["filter.0.filter"] = "severity"
            params["filter.0.quality"] = "eq"
            params["filter.0.value"] = (
                "info" if severity == "informational" else severity
            )

        data = self._get(
            "/workbenches/vulnerabilities",
            params=params,
        )

        vulnerabilities = data.get("vulnerabilities", [])

        if not isinstance(vulnerabilities, list):
            raise RuntimeError(
                "Tenable response does not contain a valid "
                "'vulnerabilities' array."
            )

        records = [
            self._normalize_finding(item)
            for item in vulnerabilities
            if isinstance(item, dict)
        ]

        return records[offset : offset + limit]

    def get_finding(
        self,
        plugin_id: str | int,
    ) -> dict[str, Any] | None:
        """Retrieve plugin-level vulnerability information by plugin ID."""
        try:
            normalized_plugin_id = int(plugin_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("plugin_id must be an integer") from exc

        if normalized_plugin_id <= 0:
            raise ValueError("plugin_id must be positive")

        data = self._get(
            f"/workbenches/vulnerabilities/"
            f"{normalized_plugin_id}/info"
        )

        info = data.get("info")

        if not isinstance(info, dict):
            return None

        return self._normalize_finding(info)

    @staticmethod
    def _normalize_finding(item: dict[str, Any]) -> dict[str, Any]:
        """Normalize the received record using the VPM360 BRD field map."""
        normalized = normalize_tenable_record(item)
        plugin_id = normalized.get("plugin_id")

        # Retain historical API keys used by callers, while ensuring the
        # field map and complete received JSON remain available in payload.
        normalized.update(
            {
                # A plugin ID is not a host-level finding ID. This legacy
                # display identifier must not be used as a database identity.
                "id": (
                    f"plugin-{plugin_id}"
                    if plugin_id is not None
                    else None
                ),
                "count": item.get("count"),
                "plugin_family": item.get("plugin_family"),
                "vulnerability_state": item.get("vulnerability_state"),
            }
        )
        return normalized
