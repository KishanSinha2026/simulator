"""API provider for BMC Helix ITSM change requests."""

import time
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class ITSMAPIProvider:
    """Read and create change requests through BMC Helix ITSM REST APIs."""

    CHANGE_CREATE_FORM = "CHG:ChangeInterface_Create"
    CHANGE_READ_FORM = "CHG:Infrastructure Change"

    # Internal application field -> BMC Helix form attribute.
    FIELD_MAPPING = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "status": "Status",
        "impact": "Impact",
        "urgency": "Urgency",
        "location_company": "Location Company",
        "detailed_description": "Detailed Description",
        "company": "Company3",
        "support_organization": "Support Organization",
        "support_group_name": "Support Group Name",
        "change_nature": "IBL_ChangeNature",
        "nature_of_change": "IBL_Nature_Of_Change",
        "application_infrastructure": "IBL_Application_Infrastructure",
        "downtime_required": "IBL_Downtime_required",
        "service_ci": "ServiceCI",
        "description": "Description",
        "environment": "Environment",
        "scheduled_start_at": "Scheduled Start Date",
        "scheduled_end_at": "Scheduled End Date",
    }

    def __init__(self) -> None:
        settings = get_settings()

        if not settings.itsm_base_url:
            raise ValueError(
                "ITSM_BASE_URL is required when ITSM_PROVIDER=api"
            )

        if not settings.itsm_username or not settings.itsm_password:
            raise ValueError(
                "ITSM_USERNAME and ITSM_PASSWORD are required "
                "when ITSM_PROVIDER=api"
            )

        self.base_url = settings.itsm_base_url.rstrip("/")
        self.timeout = settings.api_timeout_seconds
        self.verify_tls = settings.itsm_verify_tls
        self.max_retries = settings.api_max_retries

        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            verify=self.verify_tls,
            headers={"Accept": "application/json"},
        )

        try:
            self._authenticate(
                username=settings.itsm_username,
                password=settings.itsm_password.get_secret_value(),
            )
        except Exception:
            self.client.close()
            raise

    def _authenticate(self, *, username: str, password: str) -> None:
        """Authenticate with the AR System JWT login endpoint."""
        try:
            response = self.client.post(
                "/api/jwt/login",
                data={
                    "username": username,
                    "password": password,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()

        except httpx.HTTPError as exc:
            raise RuntimeError(
                "ITSM authentication failed. Check the base URL, "
                "credentials, connectivity, and API permissions."
            ) from exc

        token = response.text.strip().strip('"')

        if not token:
            raise RuntimeError(
                "ITSM authentication returned an empty token."
            )

        self.client.headers["Authorization"] = f"AR-JWT {token}"

    def close(self) -> None:
        """Release the HTTP connection pool."""
        self.client.close()

    def __enter__(self) -> "ITSMAPIProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _escape_query_value(value: Any) -> str:
        """Escape a value embedded in an AR System query expression."""
        return str(value).replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _entry_values(entry: dict[str, Any]) -> dict[str, Any]:
        """Extract the values object from a BMC entry."""
        values = entry.get("values", {})

        if not isinstance(values, dict):
            raise RuntimeError(
                "ITSM response contains an invalid entry values object."
            )

        return values

    @staticmethod
    def _to_iso_string(value: Any) -> Any:
        """Convert Python date objects to JSON-compatible ISO strings."""
        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, date):
            return value.isoformat()

        return value

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a request with bounded retries for safe GET operations.

        POST requests are not automatically retried because retrying a
        change creation after an uncertain response can create duplicates.
        """
        method = method.upper()

        if method not in {"GET", "POST"}:
            raise ValueError(
                f"Unsupported ITSM HTTP method: {method}"
            )

        attempts = self.max_retries + 1 if method == "GET" else 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = self.client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )

                if (
                    method == "GET"
                    and response.status_code
                    in (429, 500, 502, 503, 504)
                    and attempt < attempts - 1
                ):
                    retry_after = response.headers.get("Retry-After")

                    try:
                        delay = float(retry_after) if retry_after else 0
                    except ValueError:
                        delay = 0

                    if delay <= 0:
                        delay = min(2**attempt, 10)

                    time.sleep(min(delay, 30))
                    continue

                response.raise_for_status()

                if not response.content:
                    return {}

                try:
                    data = response.json()
                except ValueError as exc:
                    raise RuntimeError(
                        "ITSM returned an invalid JSON response."
                    ) from exc

                if not isinstance(data, dict):
                    raise RuntimeError(
                        "ITSM response must be a JSON object."
                    )

                return data

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if status_code in (401, 403):
                    raise RuntimeError(
                        "ITSM authentication or permission failure "
                        f"(HTTP {status_code})."
                    ) from exc

                if status_code == 404:
                    raise RuntimeError(
                        f"ITSM resource was not found: {path}"
                    ) from exc

                if status_code == 429:
                    raise RuntimeError(
                        "ITSM rate limit reached after available retries."
                    ) from exc

                raise RuntimeError(
                    f"ITSM API request failed with HTTP "
                    f"{status_code}: {path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc

                if attempt < attempts - 1:
                    time.sleep(min(2**attempt, 10))
                    continue

                break

        raise RuntimeError(
            f"ITSM request failed after {attempts} attempt(s)."
        ) from last_error

    @classmethod
    def _normalize_entry(
        cls,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        """Map a BMC change entry to the simulator's field names."""
        values = cls._entry_values(entry)

        return {
            "id": entry.get("requestId"),
            "source_change_id": values.get(
                "Infrastructure Change ID"
            ),
            "first_name": values.get("First Name"),
            "last_name": values.get("Last Name"),
            "status": values.get("Status"),
            "impact": (
                str(values["Impact"])
                if values.get("Impact") is not None
                else None
            ),
            "urgency": (
                str(values["Urgency"])
                if values.get("Urgency") is not None
                else None
            ),
            "location_company": values.get("Location Company"),
            "detailed_description": values.get(
                "Detailed Description"
            ),
            "company": values.get("Company3", values.get("Company")),
            "support_organization": values.get(
                "Support Organization"
            ),
            "support_group_name": values.get("Support Group Name"),
            "change_nature": values.get("IBL_ChangeNature"),
            "nature_of_change": values.get("IBL_Nature_Of_Change"),
            "application_infrastructure": values.get(
                "IBL_Application_Infrastructure"
            ),
            "downtime_required": values.get("IBL_Downtime_required"),
            "service_ci": values.get("ServiceCI"),
            "description": values.get("Description"),
            "environment": values.get("Environment"),
            "scheduled_start_at": values.get("Scheduled Start Date"),
            "scheduled_end_at": values.get("Scheduled End Date"),
            "source_payload": entry,
        }

    def get_change(
        self,
        change_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a change request using its external change number."""
        normalized_id = change_id.strip()

        if not normalized_id:
            raise ValueError("change_id cannot be blank")

        form = quote(self.CHANGE_READ_FORM, safe="")
        escaped_id = self._escape_query_value(normalized_id)

        query = (
            "'Infrastructure Change ID'="
            f'"{escaped_id}"'
        )

        data = self._request(
            "GET",
            f"/api/arsys/v1/entry/{form}",
            params={
                "q": query,
                "limit": 1,
            },
        )

        entries = data.get("entries", [])

        if not isinstance(entries, list):
            raise RuntimeError(
                "ITSM response does not contain a valid entries array."
            )

        if not entries or not isinstance(entries[0], dict):
            return None

        return self._normalize_entry(entries[0])

    def list_changes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List change requests with supported filters and pagination."""
        if not 1 <= limit <= 50000:
            raise ValueError("limit must be between 1 and 50000")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        supported_fields = {
            "status": "Status",
            "change_id": "Infrastructure Change ID",
            "source_change_id": "Infrastructure Change ID",
        }

        if filters:
            clauses = []

            for key, value in filters.items():
                field_name = supported_fields.get(key)

                if field_name is None:
                    raise ValueError(
                        f"Unsupported ITSM filter: {key!r}"
                    )

                escaped_value = self._escape_query_value(value)

                clauses.append(
                    f"'{field_name}'=\"{escaped_value}\""
                )

            if clauses:
                params["q"] = " AND ".join(clauses)

        form = quote(self.CHANGE_READ_FORM, safe="")

        data = self._request(
            "GET",
            f"/api/arsys/v1/entry/{form}",
            params=params,
        )

        entries = data.get("entries", [])

        if not isinstance(entries, list):
            raise RuntimeError(
                "ITSM response does not contain a valid entries array."
            )

        return [
            self._normalize_entry(entry)
            for entry in entries
            if isinstance(entry, dict)
        ]

    @classmethod
    def _map_create_values(
        cls,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Map internal application fields to BMC interface-form fields."""
        values: dict[str, Any] = {}

        for application_field, bmc_field in cls.FIELD_MAPPING.items():
            if application_field not in payload:
                continue

            value = payload[application_field]

            if value is None:
                continue

            values[bmc_field] = cls._to_iso_string(value)

        if not values.get("Description"):
            raise ValueError(
                "A non-empty description is required to create a change."
            )

        # The BMC change number is normally assigned by the target system;
        # source_change_id is deliberately not mapped into the create form.
        values["z1D_Action"] = "CREATE"

        return values

    def create_change(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a change using the configured BMC interface form.

        The target form and required fields must be verified in the
        customer's BMC Helix environment before enabling live creation.
        """
        if not payload:
            raise ValueError("Change payload cannot be empty")

        values = self._map_create_values(payload)
        form = quote(self.CHANGE_CREATE_FORM, safe="")

        # Intentionally not automatically retried: a timeout can occur
        # after BMC has created the record, so retrying may duplicate it.
        data = self._request(
            "POST",
            f"/api/arsys/v1/entry/{form}",
            json_body={"values": values},
        )

        response_values = data.get("values", {})

        if not isinstance(response_values, dict):
            response_values = {}

        return self._normalize_entry(
            {
                "requestId": data.get("requestId"),
                "values": response_values,
            }
        )