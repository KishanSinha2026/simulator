"""Read-only connection probes for configured integrations."""

from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.providers.factory import get_provider


_FIXTURE_PROBES = {
    "tenable": lambda provider: provider.list_scans(limit=1),
    "cmdb": lambda provider: provider.list_servers(limit=1),
    "itsm": lambda provider: provider.list_changes(limit=1),
    "satellite": lambda provider: provider.list_hosts(limit=1),
    "sccm": lambda provider: provider.list_devices(limit=1),
    "squad1": lambda provider: provider.list_vulnerabilities(limit=1),
    "ansible": lambda provider: provider.list_templates(limit=1),
}

_API_PROBES = {
    "tenable": lambda provider: provider.test_connection(),
    "cmdb": lambda provider: provider.get_attribute_metadata(),
    "itsm": lambda provider: provider.list_changes(limit=1),
    "satellite": lambda provider: provider.list_hosts(limit=1),
    "sccm": lambda provider: provider.list_devices(limit=1),
    "squad1": lambda provider: provider.list_vulnerabilities(limit=1),
    "ansible": lambda provider: provider.test_connection(),
}


def check_connector_connection(integration: str) -> dict[str, Any]:
    """Probe a connector without creating, changing, or importing records.

    Fixture mode verifies that local fixture data is readable and explicitly
    reports that no live vendor connection was checked.
    """
    checked_at = datetime.now(timezone.utc)
    mode = get_settings().provider_for(integration)

    try:
        provider = get_provider(integration)
        if mode == "json":
            _FIXTURE_PROBES[integration](provider)
            return {
                "integration": integration,
                "status": "fixture",
                "connected": False,
                "healthy": True,
                "provider_mode": mode,
                "checked_at": checked_at,
                "message": (
                    "Fixture data is available; no live vendor connection "
                    "was checked."
                ),
            }

        _API_PROBES[integration](provider)
        return {
            "integration": integration,
            "status": "connected",
            "connected": True,
            "healthy": True,
            "provider_mode": mode,
            "checked_at": checked_at,
            "message": "Read-only API connection check succeeded.",
        }
    except Exception as exc:
        return {
            "integration": integration,
            "status": "error",
            "connected": False,
            "healthy": False,
            "provider_mode": mode,
            "checked_at": checked_at,
            "message": str(exc),
        }
