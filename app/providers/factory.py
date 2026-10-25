
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.providers.cmdb_json import CMDBJsonProvider
from app.providers.itsm_json import ITSMJsonProvider
from app.providers.satellite_json import SatelliteJsonProvider
from app.providers.tenable_json import TenableJsonProvider


SUPPORTED_INTEGRATIONS = ("tenable", "cmdb", "itsm", "satellite")


@lru_cache(maxsize=len(SUPPORTED_INTEGRATIONS))
def get_provider(integration: str) -> Any:
    """Return the configured provider for an integration."""
    name = integration.strip().lower()

    if name not in SUPPORTED_INTEGRATIONS:
        raise ValueError(
            f"Unknown integration {integration!r}. "
            f"Supported integrations: {', '.join(SUPPORTED_INTEGRATIONS)}"
        )

    settings = get_settings()
    mode = settings.provider_for(name)

    if mode == "json":
        providers = {
            "tenable": TenableJsonProvider,
            "cmdb": CMDBJsonProvider,
            "itsm": ITSMJsonProvider,
            "satellite": SatelliteJsonProvider,
        }
        return providers[name]()

    if mode == "api":
        api_modules = {
            "tenable": "app.providers.tenable_api",
            "cmdb": "app.providers.cmdb_api",
            "itsm": "app.providers.itsm_api",
            "satellite": "app.providers.satellite_api",
        }
        class_names = {
            "tenable": "TenableAPIProvider",
            "cmdb": "CMDBAPIProvider",
            "itsm": "ITSMAPIProvider",
            "satellite": "SatelliteAPIProvider",
        }

        try:
            import importlib

            module = importlib.import_module(api_modules[name])
            provider_class = getattr(module, class_names[name])
        except (ImportError, AttributeError) as exc:
            raise RuntimeError(
                f"The {name} API provider has not been implemented yet. "
                "Keep its PROVIDER setting as 'json' until the API adapter "
                "and its tests are ready."
            ) from exc

        return provider_class()

    raise ValueError(f"Unsupported provider mode: {mode!r}")
