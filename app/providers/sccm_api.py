"""BRD-aligned SCCM 2509 AdminService API provider matching Table 20."""

from typing import Any
import httpx

from app.core.config import get_settings


class SCCMAPIProvider:
    """Interact with Configuration Manager AdminService API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.base_url = settings.sccm_base_url.rstrip("/")
        self.timeout = settings.api_timeout_seconds
        self.max_retries = settings.api_max_retries
        self.username = settings.sccm_username
        self.password = settings.sccm_password.get_secret_value() if settings.sccm_password else ""

        self.auth = (self.username, self.password) if self.username and self.password else None
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def list_devices(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query SMS_CombinedDeviceResources for client activity and inventory."""
        if not self.base_url:
            raise RuntimeError("SCCM_BASE_URL is not configured for API mode")

        url = f"{self.base_url}/AdminService/wmi/SMS_CombinedDeviceResources"
        params: dict[str, Any] = {"$top": limit, "$skip": offset}
        try:
            with httpx.Client(timeout=self.timeout, verify=self.settings.sccm_verify_tls, auth=self.auth) as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("value", []) if isinstance(data, dict) else []
        except Exception as exc:
            raise RuntimeError(f"SCCM AdminService devices request failed: {exc}") from exc

    def list_collections(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query SMS_Collection for target patching collections."""
        if not self.base_url:
            raise RuntimeError("SCCM_BASE_URL is not configured for API mode")

        url = f"{self.base_url}/AdminService/wmi/SMS_Collection"
        params: dict[str, Any] = {"$top": limit, "$skip": offset}
        try:
            with httpx.Client(timeout=self.timeout, verify=self.settings.sccm_verify_tls, auth=self.auth) as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("value", []) if isinstance(data, dict) else []
        except Exception as exc:
            raise RuntimeError(f"SCCM AdminService collections request failed: {exc}") from exc

    def list_deployments(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query SMS_UpdateGroupAssignment for deployment policies."""
        if not self.base_url:
            raise RuntimeError("SCCM_BASE_URL is not configured for API mode")

        url = f"{self.base_url}/AdminService/wmi/SMS_UpdateGroupAssignment"
        params: dict[str, Any] = {"$top": limit, "$skip": offset}
        try:
            with httpx.Client(timeout=self.timeout, verify=self.settings.sccm_verify_tls, auth=self.auth) as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("value", []) if isinstance(data, dict) else []
        except Exception as exc:
            raise RuntimeError(f"SCCM AdminService deployments request failed: {exc}") from exc
