"""Provider package for VPM360 integrations.

JSON providers support local simulation and development.
API providers connect to external systems such as Tenable,
BMC Helix CMDB, BMC Helix ITSM, and Red Hat Satellite.

Provider selection is centralized in app.providers.factory.
"""

from app.providers.factory import get_provider

__all__ = ["get_provider"]