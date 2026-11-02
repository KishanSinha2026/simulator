"""Schemas shared by connector connection-check endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConnectorConnectionResponse(BaseModel):
    """Safe connection result; never includes credentials or source payloads."""

    model_config = ConfigDict(extra="forbid")

    integration: str
    status: Literal["connected", "fixture", "error"]
    connected: bool
    healthy: bool
    provider_mode: Literal["api", "json"]
    checked_at: datetime
    message: str
    history_id: int
