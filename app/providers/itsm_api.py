
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class ITSMAPIProvider:
    """BMC Helix ITSM change-request API adapter."""

    CHANGE_CREATE_FORM = "CHG:ChangeInterface_Create"
    CHANGE_READ_FORM = "CHG:Infrastructure Change"

    def __init__(self) -> None:
        settings = get_settings()

        if not settings.itsm_base_url:
            raise ValueError("ITSM_BASE_URL is required in API mode")

        if not settings.itsm_username or not settings.itsm_password:
            raise ValueError(
                "ITSM_USERNAME and ITSM_PASSWORD are required in API mode"
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
            response = self.client.post(
                "/api/jwt/login",
                data={
                    "username": settings.itsm_username,
                    "password": settings.itsm_password.get_secret_value(),
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self.client.close()
            raise RuntimeError(
                "ITSM authentication failed. Check the base URL, "
                "credentials, and API permissions."
            ) from exc

        token = response.text.strip().strip('"')
        if not token:
            self.client.close()
            raise RuntimeError("ITSM authentication returned an empty token.")

        self.client.headers["Authorization"] = f"AR-JWT {token}"

    def close(self) -> None:
        """Release HTTP resources."""
        self.client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )

                if (
                    response.status_code in (429, 500, 502, 503, 504)
                    and attempt < self.max_retries
                ):
                    continue

                response.raise_for_status()

                if not response.content:
                    return {}

                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Unexpected JSON response from ITSM")

                return data

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code

                if status in (401, 403):
                    raise RuntimeError(
                        f"ITSM authentication or permission failure "
                        f"(HTTP {status})."
                    ) from exc

                if status == 429:
                    raise RuntimeError(
                        "ITSM API rate limit reached. Retry later."
                    ) from exc

                raise RuntimeError(
                    f"ITSM API request failed with HTTP {status}: {path}"
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break

        raise RuntimeError(
            f"ITSM request failed after {self.max_retries + 1} attempts."
        ) from last_error

    @staticmethod
    def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
        values = entry.get("values", {})
        if not isinstance(values, dict):
            values = {}

        return {
            "id": entry.get("requestId"),
            "request_id": entry.get("requestId"),
            "change_id": values.get("Infrastructure Change ID"),
            "summary": values.get("Description"),
            "status": values.get("Status"),
            "impact": values.get("Impact"),
            "urgency": values.get("Urgency"),
            "values": values,
            "source_payload": entry,
        }

    def get_change(self, change_id: str) -> dict[str, Any] | None:
        """Retrieve a change request by its change number."""
        form = quote(self.CHANGE_READ_FORM, safe="")
        query = (
            "'Infrastructure Change ID'="
            f'"{change_id.replace(chr(34), chr(92) + chr(34))}"'
        )

        data = self._request(
            "GET",
            f"/api/arsys/v1/entry/{form}",
            params={"q": query, "limit": 1},
        )

        entries = data.get("entries", [])
        if not isinstance(entries, list) or not entries:
            return None

        entry = entries[0]
        if not isinstance(entry, dict):
            return None

        return self._normalize_entry(entry)

    def list_changes(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve change requests, with optional server-side filtering."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        if filters:
            supported_fields = {
                "status": "Status",
                "change_id": "Infrastructure Change ID",
            }
            clauses = []

            for key, value in filters.items():
                field = supported_fields.get(key)
                if field is None:
                    raise ValueError(
                        f"Unsupported ITSM filter: {key!r}"
                    )

                escaped_value = str(value).replace("\\", "\\\\").replace(
                    '"', '\\"'
                )
                clauses.append(f"'{field}'=\"{escaped_value}\"")

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
            raise ValueError(
                "ITSM response does not contain a valid 'entries' array."
            )

        return [
            self._normalize_entry(entry)
            for entry in entries
            if isinstance(entry, dict)
        ]

    def create_change(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a change request using the BMC interface form."""
        if not payload:
            raise ValueError("Change payload cannot be empty")

        # The caller must map and validate BRD fields before this call.
        values = dict(payload)
        values.setdefault("z1D_Action", "CREATE")

        form = quote(self.CHANGE_CREATE_FORM, safe="")
        data = self._request(
            "POST",
            f"/api/arsys/v1/entry/{form}",
            json_body={"values": values},
        )

        return {
            "id": data.get("requestId"),
            "values": data.get("values", {}),
            "source_payload": data,
        }
