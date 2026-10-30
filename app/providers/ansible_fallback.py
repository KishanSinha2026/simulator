"""Fallback orchestration for Ansible API and fixture providers."""

from typing import Any

from app.providers.ansible_json import AnsibleJsonProvider


class AnsibleAPIUnavailable(RuntimeError):
    """The controller cannot be reached; authentication errors are excluded."""


class AnsibleFallbackProvider:
    """Use JSON fixtures only when the live AAP API is unreachable."""

    def __init__(self, api_provider: Any, fallback_provider: AnsibleJsonProvider) -> None:
        self.api_provider = api_provider
        self.fallback_provider = fallback_provider

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return getattr(self.api_provider, method)(*args, **kwargs)
        except AnsibleAPIUnavailable:
            return getattr(self.fallback_provider, method)(*args, **kwargs)

    def list_templates(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self._call("list_templates", limit=limit, offset=offset)

    def test_connection(self) -> dict[str, Any]:
        try:
            return self.api_provider.test_connection()
        except AnsibleAPIUnavailable:
            return self.fallback_provider.test_connection()

    def launch_job(self, template_id: str, *, limit: str | None, extra_vars: dict[str, Any]) -> dict[str, Any]:
        return self._call("launch_job", template_id, limit=limit, extra_vars=extra_vars)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._call("get_job", job_id)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._call("cancel_job", job_id)
