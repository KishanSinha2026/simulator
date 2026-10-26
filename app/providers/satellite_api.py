"""API provider for Red Hat Satellite 6.9."""

import time
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class SatelliteAPIProvider:
    """Access hosts and remote-execution jobs through Satellite's REST API."""

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self) -> None:
        settings = get_settings()

        if not settings.satellite_base_url:
            raise ValueError(
                "SATELLITE_BASE_URL is required in API mode."
            )

        if (
            not settings.satellite_username
            or not settings.satellite_password
        ):
            raise ValueError(
                "SATELLITE_USERNAME and SATELLITE_PASSWORD "
                "are required in API mode."
            )

        if settings.api_timeout_seconds <= 0:
            raise ValueError(
                "API_TIMEOUT_SECONDS must be greater than zero."
            )

        if settings.api_max_retries < 0:
            raise ValueError(
                "API_MAX_RETRIES cannot be negative."
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
        """Release the HTTP connection pool."""
        self.client.close()

    def __enter__(self) -> "SatelliteAPIProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        """Return a bounded retry delay, honoring Retry-After when possible."""
        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                delay = float(retry_after)
                if delay >= 0:
                    return min(delay, 30.0)
            except ValueError:
                # Retry-After may be an HTTP date rather than a number.
                pass

        return min(2**attempt, 10.0)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an API request.

        Only GET requests are retried. Retrying POST requests could launch
        a duplicate remote-execution job if the server processed the
        operation but the client lost the response.
        """
        method = method.upper()

        if method not in {"GET", "POST"}:
            raise ValueError(
                f"Unsupported Satellite HTTP method: {method}"
            )

        attempts = self.max_retries + 1 if method == "GET" else 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = self.client.request(
                    method,
                    path,
                    params=params,
                    json=payload,
                )

                if (
                    method == "GET"
                    and response.status_code in self.RETRYABLE_STATUS_CODES
                    and attempt < attempts - 1
                ):
                    time.sleep(self._retry_delay(response, attempt))
                    continue

                response.raise_for_status()

                if not response.content:
                    return {}

                try:
                    data = response.json()
                except ValueError as exc:
                    raise RuntimeError(
                        "Satellite returned an invalid JSON response."
                    ) from exc

                if not isinstance(data, dict):
                    raise RuntimeError(
                        "Satellite response must be a JSON object."
                    )

                return data

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code

                if status in (401, 403):
                    raise RuntimeError(
                        "Satellite authentication or permission failure "
                        f"(HTTP {status})."
                    ) from exc

                if status == 404:
                    raise RuntimeError(
                        f"Satellite resource was not found: {path}"
                    ) from exc

                if status == 429:
                    raise RuntimeError(
                        "Satellite API rate limit reached. "
                        "Retry later or reduce request frequency."
                    ) from exc

                raise RuntimeError(
                    f"Satellite API request failed with HTTP "
                    f"{status}: {path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc

                if attempt < attempts - 1:
                    time.sleep(min(2**attempt, 10.0))
                    continue

                break

        raise RuntimeError(
            f"Satellite request failed after {attempts} attempt(s)."
        ) from last_error

    @staticmethod
    def _results(
        data: dict[str, Any],
        key: str,
    ) -> list[dict[str, Any]]:
        """Extract a list of result objects from an API response."""
        results = data.get(key, [])

        if not isinstance(results, list):
            raise RuntimeError(
                f"Satellite response does not contain a valid "
                f"{key!r} array."
            )

        return [
            item for item in results
            if isinstance(item, dict)
        ]

    @staticmethod
    def _validate_pagination(*, limit: int, page: int) -> None:
        if not 1 <= limit <= 50000:
            raise ValueError("limit must be between 1 and 50000")

        if page < 1:
            raise ValueError("page must be at least 1")

    @staticmethod
    def _encode_identifier(identifier: str | int) -> str:
        """Validate and URL-encode a Satellite resource identifier."""
        value = str(identifier).strip()

        if not value:
            raise ValueError("Resource identifier cannot be blank")

        return quote(value, safe="")

    def list_hosts(
        self,
        *,
        search: str | None = None,
        limit: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """List registered hosts using Satellite search syntax."""
        self._validate_pagination(limit=limit, page=page)

        params: dict[str, Any] = {
            "per_page": limit,
            "page": page,
        }

        if search is not None:
            search = search.strip()
            if search:
                params["search"] = search

        data = self._request(
            "GET",
            "/api/v2/hosts",
            params=params,
        )

        return self._results(data, "results")

    def get_host(self, host_id: str | int) -> dict[str, Any]:
        """Retrieve one registered host by its Satellite identifier."""
        identifier = self._encode_identifier(host_id)

        return self._request(
            "GET",
            f"/api/v2/hosts/{identifier}",
        )

    def list_job_templates(
        self,
        *,
        search: str | None = None,
        limit: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """List available remote-execution job templates."""
        self._validate_pagination(limit=limit, page=page)

        params: dict[str, Any] = {
            "per_page": limit,
            "page": page,
        }

        if search is not None:
            search = search.strip()
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
        self._validate_pagination(limit=limit, page=page)

        data = self._request(
            "GET",
            "/api/job_invocations",
            params={
                "per_page": limit,
                "page": page,
            },
        )

        return self._results(data, "results")

    def get_job_run(
        self,
        job_run_id: str | int,
    ) -> dict[str, Any]:
        """Retrieve invocation details and status."""
        identifier = self._encode_identifier(job_run_id)

        return self._request(
            "GET",
            f"/api/job_invocations/{identifier}",
        )

    def get_host_job_result(
        self,
        job_run_id: str | int,
        host_id: str | int,
    ) -> dict[str, Any]:
        """Retrieve an invocation result for one host."""
        job_id = self._encode_identifier(job_run_id)
        host = self._encode_identifier(host_id)

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
        """Launch a real Satellite remote-execution job.

        This may execute commands on matching hosts. The calling service
        must enforce authorization, target validation, and approval
        requirements before invoking this method.
        """
        if isinstance(template_id, bool) or template_id < 1:
            raise ValueError(
                "template_id must be a positive integer."
            )

        if not isinstance(search_query, str) or not search_query.strip():
            raise ValueError(
                "A non-empty Satellite host search query is required."
            )

        if inputs is not None and not isinstance(inputs, dict):
            raise ValueError("inputs must be a dictionary.")

        payload = {
            "job_invocation": {
                "job_template_id": template_id,
                "search_query": search_query.strip(),
                "inputs": inputs or {},
            }
        }

        return self._request(
            "POST",
            "/api/job_invocations",
            payload=payload,
        )

    def cancel_job(
        self,
        job_run_id: str | int,
    ) -> dict[str, Any]:
        """Request cancellation of a running job invocation."""
        identifier = self._encode_identifier(job_run_id)

        return self._request(
            "POST",
            f"/api/job_invocations/{identifier}/cancel",
            payload={},
        )