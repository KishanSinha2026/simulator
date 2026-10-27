"""BRD-aligned Squad1 API provider matching Table 12 contract."""

from typing import Any
import httpx

from app.core.config import get_settings


class Squad1APIProvider:
    """Retrieve Squad1 vulnerability records matching BRD Table 12."""

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.base_url = settings.squad1_base_url.rstrip("/")
        self.timeout = settings.api_timeout_seconds
        self.max_retries = settings.api_max_retries
        api_key = settings.squad1_api_key.get_secret_value() if settings.squad1_api_key else ""

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def list_vulnerabilities(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List vulnerabilities from remote Squad1 endpoint."""
        if not self.base_url:
            raise RuntimeError("SQUAD1_BASE_URL is not configured for API mode")

        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if filters:
            params.update(filters)

        url = f"{self.base_url}/api/v1/vulnerabilities"
        try:
            with httpx.Client(timeout=self.timeout, verify=self.settings.squad1_verify_tls) as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                # BRD Table 12: JSON object with statusCode, statusMessage and data array
                if isinstance(data, dict) and "data" in data:
                    return data["data"]
                if isinstance(data, list):
                    return data
                return []
        except Exception as exc:
            raise RuntimeError(f"Squad1 API request failed: {exc}") from exc

    def create_vulnerability(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Post a vulnerability record to remote Squad1 endpoint."""
        if not self.base_url:
            raise RuntimeError("SQUAD1_BASE_URL is not configured for API mode")

        url = f"{self.base_url}/api/v1/vulnerabilities"
        try:
            with httpx.Client(timeout=self.timeout, verify=self.settings.squad1_verify_tls) as client:
                response = client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            raise RuntimeError(f"Squad1 API create failed: {exc}") from exc
