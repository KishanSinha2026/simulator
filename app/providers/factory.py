"""Factory for configured integration providers."""

import importlib
import logging
from threading import RLock
from typing import Any

from app.core.config import get_settings
from app.providers.cmdb_json import CMDBJsonProvider
from app.providers.itsm_json import ITSMJsonProvider
from app.providers.satellite_json import SatelliteJsonProvider
from app.providers.tenable_json import TenableJsonProvider

logger = logging.getLogger(__name__)

SUPPORTED_INTEGRATIONS = (
    "tenable",
    "cmdb",
    "itsm",
    "satellite",
)

JSON_PROVIDER_CLASSES = {
    "tenable": TenableJsonProvider,
    "cmdb": CMDBJsonProvider,
    "itsm": ITSMJsonProvider,
    "satellite": SatelliteJsonProvider,
}

API_PROVIDER_MODULES = {
    "tenable": (
        "app.providers.tenable_api",
        "TenableAPIProvider",
    ),
    "cmdb": (
        "app.providers.cmdb_api",
        "CMDBAPIProvider",
    ),
    "itsm": (
        "app.providers.itsm_api",
        "ITSMAPIProvider",
    ),
    "satellite": (
        "app.providers.satellite_api",
        "SatelliteAPIProvider",
    ),
}

_provider_cache: dict[str, Any] = {}
_provider_lock = RLock()


def _normalize_integration(integration: str) -> str:
    """Normalize and validate an integration name."""
    if not isinstance(integration, str):
        raise TypeError("integration must be a string")

    name = integration.strip().lower()

    if not name:
        raise ValueError("integration cannot be empty")

    if name not in SUPPORTED_INTEGRATIONS:
        raise ValueError(
            f"Unknown integration {integration!r}. "
            f"Supported integrations: "
            f"{', '.join(SUPPORTED_INTEGRATIONS)}"
        )

    return name


def _build_provider(integration: str) -> Any:
    """Create a provider using the current application settings."""
    settings = get_settings()
    mode = settings.provider_for(integration)

    if mode == "json":
        provider_class = JSON_PROVIDER_CLASSES[integration]
        return provider_class()

    if mode == "api":
        module_name, class_name = API_PROVIDER_MODULES[integration]

        try:
            module = importlib.import_module(module_name)
            provider_class = getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            raise RuntimeError(
                f"The {integration} API provider could not be loaded. "
                f"Verify that {module_name}.{class_name} exists "
                "and that its dependencies are installed."
            ) from exc

        return provider_class()

    raise ValueError(
        f"Unsupported provider mode {mode!r} "
        f"for integration {integration!r}"
    )


def get_provider(integration: str) -> Any:
    """Return the cached provider for the selected integration.

    A provider is created only once per integration until the cache is
    cleared. Provider creation is protected by a lock so concurrent
    requests do not create duplicate clients.
    """
    name = _normalize_integration(integration)

    with _provider_lock:
        provider = _provider_cache.get(name)

        if provider is not None:
            return provider

        provider = _build_provider(name)
        _provider_cache[name] = provider

        logger.debug(
            "Initialized provider for integration '%s'",
            name,
        )

        return provider


def clear_provider_cache() -> None:
    """Close cached providers and clear the provider cache.

    Call this during application shutdown or after changing provider
    configuration. Providers are removed from the cache before they
    are closed, so subsequent calls can construct fresh instances.
    """
    with _provider_lock:
        providers = list(_provider_cache.items())
        _provider_cache.clear()

    close_errors: list[tuple[str, Exception]] = []

    for name, provider in providers:
        close = getattr(provider, "close", None)

        if not callable(close):
            continue

        try:
            close()
            logger.debug(
                "Closed provider for integration '%s'",
                name,
            )
        except Exception as exc:
            close_errors.append((name, exc))
            logger.exception(
                "Failed to close provider for integration '%s'",
                name,
            )

    if close_errors:
        failed_names = ", ".join(
            name for name, _ in close_errors
        )
        raise RuntimeError(
            f"Failed to close providers: {failed_names}"
        ) from close_errors[0][1]


def get_cached_integrations() -> tuple[str, ...]:
    """Return the names of currently cached integrations."""
    with _provider_lock:
        return tuple(sorted(_provider_cache))