"""Public request and response schemas for Ansible Automation Platform."""

from datetime import datetime
import ipaddress
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnsibleConnectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connected: bool
    controller: str | None = None
    api_version: str | None = None
    provider_mode: str = "api"
    fallback_reason: str | None = None


class AnsibleLaunchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_template_id: str = Field(min_length=1, max_length=100)
    limit: str = Field(min_length=1, max_length=2000)
    extra_vars: dict[str, Any] = Field(default_factory=dict)

    @field_validator("limit")
    @classmethod
    def normalize_limit(cls, value: str) -> str:
        tokens = [token.strip() for token in value.split(",")]
        if not tokens or any(not token for token in tokens):
            raise ValueError("A non-empty host limit is required for a patch job")
        normalized: list[str] = []
        for token in tokens:
            if token.casefold() in {"all", "*"}:
                raise ValueError("Broad Ansible host patterns are not allowed for patch jobs")
            valid_hostname = bool(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", token))
            try:
                ipaddress.ip_address(token)
                valid_ip = True
            except ValueError:
                valid_ip = False
            if not (valid_hostname or valid_ip):
                raise ValueError("Use an exact hostname or IP address in the host limit")
            if token.casefold() not in {item.casefold() for item in normalized}:
                normalized.append(token)
        return ",".join(normalized)


class AnsibleJobTemplateResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int | str
    name: str
    description: str | None = None
    ask_limit_on_launch: bool | None = None
    ask_variables_on_launch: bool | None = None


class AnsibleJobTemplateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AnsibleJobTemplateResponse]
    count: int = Field(ge=0)
    next: str | None = None


class AnsibleJobLaunchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    job_id: str
    status: str
    job_template_id: str
    simulated: bool = False


class AnsibleJobRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    job_id: str
    job_template_id: str
    status: str
    limit: str | None = None
    extra_vars: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    source_payload: dict[str, Any] | None = None


class AnsibleJobCancelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    job_id: str
    status: str
