
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class SatelliteAPIProvider:
    """Red Hat Satellite 6.9 REST API adapter."""

    def __init__(self) -> None:
        settings = get_settings()

        if not settings.satellite_base_url:
            raise ValueError(
                "SATELLITE_BASE_URL is required in API mode"
            )

        if not settings.satellite_username or not settings.satellite_password:
            raise ValueError(
                "SATELLITE_USERNAME and SATELLITE_PASSWORD "
                "are required in API mode"
            )

        self.base_url = settings.satellite_base_url.rstrip("/")
        self.timeout = settings.api_timeout_seconds
        self.max_retries = settings.api_max_retries

        self.client = httpx.Client(
            base_url=self.base_url,
            auth=(
                settings.satellite_username,
                settings.satellite_password.get_secret_value(),
            ),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
            verify=settings.satellite_verify_tls,
        )

    def close(self) -> None:
        """Release HTTP resources."""
        self.client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(
                    method,
                    path,
                    params=params,
                    json=payload,
                )

                if (
                    response.status_code in (429, 500, 502, 503, 504)
                    and attempt < self.max_retries
                ):
                    continue

                response.raise_for_status()

                if not response.content:
                    return {}

                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError(
                        "Unexpected JSON response from Satellite"
                    )

                return data

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code

                if status in (401, 403):
                    raise RuntimeError(
                        f"Satellite authentication or permission failure "
                        f"(HTTP {status})."
                    ) from exc

                if status == 404:
                    raise RuntimeError(
                        f"Satellite resource was not found: {path}"
                    ) from exc

                if status == 429:
                    raise RuntimeError(
                        "Satellite API rate limit reached."
                    ) from exc

                raise RuntimeError(
                    f"Satellite API request failed with HTTP {status}: "
                    f"{path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break

        raise RuntimeError(
            f"Satellite request failed after {self.max_retries + 1} attempts."
        ) from last_error

    @staticmethod
    def _results(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
        results = data.get(key, [])

        if not isinstance(results, list):
            raise ValueError(
                f"Satellite response does not contain a valid {key!r} array."
            )

        return [item for item in results if isinstance(item, dict)]

    def list_hosts(
        self,
        *,
        search: str | None = None,
        limit: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """List registered hosts, optionally using Satellite search syntax."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        if page < 1:
            raise ValueError("page must be at least 1")

        params: dict[str, Any] = {
            "per_page": limit,
            "page": page,
        }
        if search:
            params["search"] = search

        data = self._request("GET", "/api/v2/hosts", params=params)
        return self._results(data, "results")

    def get_host(self, host_id: str | int) -> dict[str, Any]:
        """Retrieve one host by Satellite ID or supported host identifier."""
        identifier = quote(str(host_id), safe="")
        return self._request("GET", f"/api/v2/hosts/{identifier}")

    def list_job_templates(
        self,
        *,
        search: str | None = None,
        limit: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """List remote-execution job templates."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        if page < 1:
            raise ValueError("page must be at least 1")

        params: dict[str, Any] = {
            "per_page": limit,
            "page": page,
        }
        if search:
            params["search"] = search

        data = self._request(
            "GET",
            "/api/v2/job_templates",
            params=params,
        )
        return self._results(data, "results")

    def list_job_runs(
        self,
        *,
        limit: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """List remote-execution job invocations."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        if page < 1:
            raise ValueError("page must be at least 1")

        data = self._request(
            "GET",
            "/api/job_invocations",
            params={"per_page": limit, "page": page},
        )
        return self._results(data, "results")

    def get_job_run(self, job_run_id: str | int) -> dict[str, Any]:
        """Retrieve invocation details and status."""
        identifier = quote(str(job_run_id), safe="")
        return self._request(
            "GET",
            f"/api/job_invocations/{identifier}",
        )

    def get_host_job_result(
        self,
        job_run_id: str | int,
        host_id: str | int,
    ) -> dict[str, Any]:
        """Retrieve the result for one host in an invocation."""
        job_id = quote(str(job_run_id), safe="")
        host = quote(str(host_id), safe="")

        return self._request(
            "GET",
            f"/api/job_invocations/{job_id}/hosts/{host}",
        )

    def launch_job(
        self,
        *,
        template_id: int,
        search_query: str,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Launch a real Satellite job invocation.

        This can execute commands on targeted hosts. Call only after
        authorization, target validation, and approval checks.
        """
        if template_id < 1:
            raise ValueError("template_id must be a positive integer")

        if not search_query.strip():
            raise ValueError(
                "A non-empty Satellite host search query is required"
            )

        payload = {
            "job_invocation": {
                "job_template_id": template_id,
                "search_query": search_query,
                "inputs": inputs or {},
            }
        }

        return self._request(
            "POST",
            "/api/job_invocations",
            payload=payload,
        )

    def cancel_job(self, job_run_id: str | int) -> dict[str, Any]:
        """Request cancellation of an existing job invocation."""
        identifier = quote(str(job_run_id), safe="")

        return self._request(
            "POST",
            f"/api/job_invocations/{identifier}/cancel",
            payload={},
        )
