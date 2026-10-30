"""Factory for configured integration providers."""

import logging
from dataclasses import dataclass
from importlib import import_module
from threading import RLock
from typing import Any

from app.core.config import get_settings
from app.providers.ansible_json import AnsibleJsonProvider
from app.providers.cmdb_json import CMDBJsonProvider
from app.providers.itsm_json import ITSMJsonProvider
from app.providers.satellite_json import SatelliteJsonProvider
from app.providers.sccm_json import SCCMJsonProvider
from app.providers.squad1_json import Squad1JsonProvider
from app.providers.tenable_json import TenableJsonProvider

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ProviderRegistration:
    """Construction metadata for one integration provider family."""

    api_module: str
    api_class: str
    json_class: type[Any] | None = None


# One registry is the extension point for integration providers. API-only
# integrations set json_class=None instead of requiring special-case logic.
PROVIDER_REGISTRY: dict[str, ProviderRegistration] = {
    "tenable": ProviderRegistration(
        "app.providers.tenable_api", "TenableAPIProvider", TenableJsonProvider
    ),
    "cmdb": ProviderRegistration(
        "app.providers.cmdb_api", "CMDBAPIProvider", CMDBJsonProvider
    ),
    "itsm": ProviderRegistration(
        "app.providers.itsm_api", "ITSMAPIProvider", ITSMJsonProvider
    ),
    "satellite": ProviderRegistration(
        "app.providers.satellite_api", "SatelliteAPIProvider", SatelliteJsonProvider
    ),
    "squad1": ProviderRegistration(
        "app.providers.squad1_api", "Squad1APIProvider", Squad1JsonProvider
    ),
    "sccm": ProviderRegistration(
        "app.providers.sccm_api", "SCCMAPIProvider", SCCMJsonProvider
    ),
    "ansible": ProviderRegistration(
        "app.providers.ansible_api", "AnsibleAPIProvider", AnsibleJsonProvider
    ),
}

SUPPORTED_INTEGRATIONS = tuple(PROVIDER_REGISTRY)

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
    registration = PROVIDER_REGISTRY[integration]

    if mode == "json":
        if registration.json_class is None:
            raise ValueError(
                f"{integration} requires API mode; no JSON provider is available"
            )
        return registration.json_class()

    if mode == "api":
        try:
            module = import_module(registration.api_module)
            provider_class = getattr(module, registration.api_class)
            return provider_class()
        except (ImportError, AttributeError) as exc:
            raise RuntimeError(
                f"The {integration} API provider could not be loaded. "
                f"Verify that {registration.api_module}."
                f"{registration.api_class} exists "
                "and that its dependencies are installed."
            ) from exc

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
