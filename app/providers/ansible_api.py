"""Client for Ansible Automation Platform / AWX REST API v2."""

from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class AnsibleAPIProvider:
    """Use a configured bearer API key for AWX/AAP job operations."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.ansible_base_url or not settings.ansible_api_key:
            raise ValueError("ANSIBLE_BASE_URL and ANSIBLE_API_KEY are required in API mode")
        api_prefix = "/" + settings.ansible_api_prefix.strip("/")
        self.client = httpx.Client(
            base_url=settings.ansible_base_url.rstrip("/") + api_prefix + "/",
            headers={
                "Authorization": f"Bearer {settings.ansible_api_key.get_secret_value()}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=settings.api_timeout_seconds,
            verify=settings.ansible_verify_tls,
        )

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _id(value: str | int) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("Ansible resource ID cannot be blank")
        return quote(value, safe="")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in (401, 403):
                raise RuntimeError(f"Ansible authentication or permission failure (HTTP {code})") from exc
            if code == 404:
                raise RuntimeError("Ansible resource was not found") from exc
            raise RuntimeError(f"Ansible API request failed (HTTP {code})") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Ansible API request failed due to a connection error") from exc
        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("Ansible returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Ansible response must be a JSON object")
        return data

    def list_templates(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """List templates while translating VPM offset/limit to AAP pages."""
        if not 1 <= limit <= 50000 or offset < 0:
            raise ValueError("limit must be between 1 and 50000 and offset cannot be negative")
        # AAP controller uses page pagination; gateway versions reject offset.
        page_size = min(limit, 200)
        page = offset // page_size + 1
        skip = offset % page_size
        results: list[dict[str, Any]] = []
        total = 0
        has_next = False
        while len(results) < limit:
            data = self._request(
                "GET", "job_templates/",
                params={"page_size": page_size, "page": page},
            )
            batch = data.get("results", [])
            if not isinstance(batch, list):
                raise RuntimeError("Ansible template response has an invalid results array")
            total = int(data.get("count") or 0)
            if skip:
                batch = batch[skip:]
                skip = 0
            results.extend(item for item in batch if isinstance(item, dict))
            has_next = bool(data.get("next"))
            if not has_next or not batch:
                break
            page += 1
        results = results[:limit]
        next_offset = offset + len(results)
        return {
            "results": results,
            "count": total,
            "next": f"?offset={next_offset}" if has_next and next_offset < total else None,
        }

    def test_connection(self) -> dict[str, Any]:
        """Check API authentication and basic access to the controller."""
        return self._request("GET", "")

    def launch_job(self, template_id: str, *, limit: str | None, extra_vars: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {"extra_vars": extra_vars}
        if limit:
            body["limit"] = limit
        return self._request("POST", f"job_templates/{self._id(template_id)}/launch/", json=body)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"jobs/{self._id(job_id)}/")

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"jobs/{self._id(job_id)}/cancel/", json={})
