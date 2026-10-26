"""Compatibility imports for BMC Helix ITSM SQLAlchemy models.

The canonical model definitions remain in app.models.istm.
This module preserves the correctly spelled import path used by
services, repositories, and Alembic.
"""

from app.models.istm import (
    ITSMChange,
    ITSMChangeHistory,
    ITSMWorklog,
)

__all__ = [
    "ITSMChange",
    "ITSMChangeHistory",
    "ITSMWorklog",
]