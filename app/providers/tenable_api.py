"""BRD-aligned Tenable API provider."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.providers.tenable_normalizer import normalize_tenable_record


class TenableAPIProvider:
    """Retrieve Tenable scan and finding details using the approved API contract."""

    WRAPPER_KEYS = (
        "data",
        "results",
        "items",
        "response",
        "scanResult",
        "scanResults",
        "analysis",
        "result",
        "details",
    )

    def __init__(self) -> None:
        settings = get_settings()

        self.settings = settings
        self.base_url = settings.tenable_base_url.rstrip("/")
        self.timeout = settings.api_timeout_seconds
        self.max_retries = settings.api_max_retries

        access_key = (
            settings.tenable_access_key.get_secret_value()
            if settings.tenable_access_key
            else ""
        )
        secret_key = (
            settings.tenable_secret_key.get_secret_value()
            if settings.tenable_secret_key
            else ""
        )

        missing: list[str] = []

        if not self.base_url:
            missing.append("TENABLE_BASE_URL")
        if not access_key:
            missing.append("TENABLE_ACCESS_KEY")
        if not settings.tenable_auth_header_name.strip():
            missing.append("TENABLE_AUTH_HEADER_NAME")
        if settings.tenable_scan_result_method is None:
            missing.append("TENABLE_SCAN_RESULT_METHOD")
        if settings.tenable_analysis_method is None:
            missing.append("TENABLE_ANALYSIS_METHOD")
        if not settings.tenable_analysis_id_param.strip():
            missing.append("TENABLE_ANALYSIS_ID_PARAM")
        if settings.tenable_analysis_id_location is None:
            missing.append("TENABLE_ANALYSIS_ID_LOCATION")
        if settings.tenable_scan_result_paging_mode is None:
            missing.append("TENABLE_SCAN_RESULT_PAGING_MODE")

        if (
            settings.tenable_scan_result_paging_mode == "offset_limit"
            and not settings.tenable_scan_result_offset_param.strip()
        ):
            missing.append("TENABLE_SCAN_RESULT_OFFSET_PARAM")

        if (
            settings.tenable_scan_result_paging_mode == "offset_limit"
            and not settings.tenable_scan_result_limit_param.strip()
        ):
            missing.append("TENABLE_SCAN_RESULT_LIMIT_PARAM")

        if missing:
            raise ValueError(
                "Tenable API mode is not activated. Confirm the client API "
                "contract and configure: " + ", ".join(missing)
            )

        auth_header_name = settings.tenable_auth_header_name.strip()
        auth_prefix = settings.tenable_auth_header_prefix

        if auth_header_name.casefold() == "x-apikeys":
            if not secret_key:
                raise ValueError(
                    "TENABLE_SECRET_KEY is required when the approved "
                    "authentication header is X-ApiKeys."
                )

            auth_value = (
                f"accessKey={access_key}; secretKey={secret_key}"
            )
        else:
            auth_value = f"{auth_prefix}{access_key}"

        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Accept": "application/json",
                auth_header_name: auth_value,
            },
            timeout=self.timeout,
            verify=settings.tenable_verify_tls,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def __enter__(self) -> "TenableAPIProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Request JSON with bounded retries and sanitized errors."""
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
                    response.status_code == 429
                    or response.status_code >= 500
                ):
                    if attempt < self.max_retries:
                        retry_after = response.headers.get("Retry-After")

                        try:
                            delay = (
                                float(retry_after)
                                if retry_after
                                else min(2**attempt, 10)
                            )
                        except ValueError:
                            delay = min(2**attempt, 10)

                        time.sleep(max(0, min(delay, 30)))
                        continue

                response.raise_for_status()

                try:
                    return response.json()
                except ValueError as exc:
                    raise RuntimeError(
                        f"Tenable returned non-JSON content for {path}."
                    ) from exc

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if status_code in (401, 403):
                    raise RuntimeError(
                        "Tenable authentication or permission failure "
                        f"(HTTP {status_code}). Verify the approved client "
                        "authentication method and account permissions."
                    ) from exc

                if status_code == 429:
                    raise RuntimeError(
                        "Tenable rate limit reached after retries."
                    ) from exc

                raise RuntimeError(
                    f"Tenable API request failed with HTTP {status_code} "
                    f"for {path}."
                ) from exc

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc

                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue

                break

        raise RuntimeError(
            f"Tenable request to {path} failed after "
            f"{self.max_retries + 1} attempts."
        ) from last_error

    @classmethod
    def _extract_records(
        cls,
        payload: Any,
        *,
        record_kind: str,
        depth: int = 0,
    ) -> list[dict[str, Any]]:
        """Extract records from common JSON wrappers without accepting
        an unrecognized object as an empty result set.
        """
        if depth > 8:
            raise RuntimeError(
                "Tenable response nesting exceeds the supported depth."
            )

        if isinstance(payload, list):
            if not all(isinstance(item, dict) for item in payload):
                raise RuntimeError(
                    "Tenable response array contains non-object entries."
                )
            return payload

        if not isinstance(payload, dict):
            raise RuntimeError(
                "Tenable returned an unexpected response shape."
            )

        normalized_keys = {
            "".join(ch.lower() for ch in str(key) if ch.isalnum())
            for key in payload
        }

        if record_kind == "scan":
            record_markers = {
                "starttime",
                "finishtime",
                "scanduration",
                "resulttype",
            }
        else:
            record_markers = {
                "plugin",
                "pluginid",
                "pluginname",
                "ipaddress",
                "cvssv3basescore",
                "cvss3basescore",
            }

        if normalized_keys.intersection(record_markers):
            return [payload]

        # Recognize explicit empty list responses.
        for key in cls.WRAPPER_KEYS:
            value = payload.get(key)
            if isinstance(value, list) and not value:
                return []

        candidates: list[list[dict[str, Any]]] = []

        for key in cls.WRAPPER_KEYS:
            if key not in payload:
                continue

            value = payload[key]

            if isinstance(value, (list, dict)):
                candidates.append(
                    cls._extract_records(
                        value,
                        record_kind=record_kind,
                        depth=depth + 1,
                    )
                )

        if candidates:
            non_empty = [candidate for candidate in candidates if candidate]

            if len(non_empty) > 1:
                raise RuntimeError(
                    "Tenable response contains multiple possible record "
                    "collections. Confirm the response envelope before import."
                )

            return non_empty[0] if non_empty else []

        raise RuntimeError(
            f"Unable to identify the {record_kind} record collection in "
            "the Tenable response. The import was not treated as empty."
        )

    def _fetch_scan_result_page(
        self,
        *,
        offset: int,
    ) -> list[dict[str, Any]]:
        settings = self.settings

        params: dict[str, Any] = {
            "fields": settings.tenable_scan_result_fields,
        }

        if settings.tenable_scan_result_paging_mode == "offset_limit":
            params[settings.tenable_scan_result_offset_param] = offset
            params[settings.tenable_scan_result_limit_param] = (
                settings.tenable_scan_result_page_size
            )

        payload = self._request_json(
            settings.tenable_scan_result_method,
            settings.tenable_scan_result_path,
            params=params,
        )

        return self._extract_records(
            payload,
            record_kind="scan",
        )

    def _fetch_all_scans(self) -> list[dict[str, Any]]:
        """Fetch scan records using the configured, client-confirmed paging mode."""
        settings = self.settings
        scans: list[dict[str, Any]] = []

        if settings.tenable_scan_result_paging_mode == "none":
            page = self._fetch_scan_result_page(offset=0)

            if len(page) >= settings.tenable_max_scan_results:
                raise RuntimeError(
                    "The unpaged scanResult response reached the configured "
                    "safety limit. Confirm paging and increase limits only "
                    "after validating the client API contract."
                )

            return page

        offset = 0
        page_size = settings.tenable_scan_result_page_size

        while True:
            page = self._fetch_scan_result_page(offset=offset)

            if not page:
                break

            if len(scans) + len(page) > settings.tenable_max_scan_results:
                raise RuntimeError(
                    "Tenable scan import exceeded TENABLE_MAX_SCAN_RESULTS. "
                    "No partial result set will be reported as complete."
                )

            scans.extend(page)

            if len(page) < page_size:
                break

            offset += page_size

        return scans

    def list_scans(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List Tenable scans retrieved from the API provider."""
        scans = self._fetch_all_scans()
        return scans[offset : offset + limit]


    def _fetch_analysis(
        self,
        scan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch detailed scanner records for one scan-result record."""
        settings = self.settings
        source_scan_id = scan.get("id")

        if source_scan_id is None or not str(source_scan_id).strip():
            raise RuntimeError(
                "A scanResult record has no source 'id'; the analysis route "
                "cannot be called safely without its scan identifier."
            )

        location = settings.tenable_analysis_id_location
        parameter = settings.tenable_analysis_id_param
        value = str(source_scan_id)

        params: dict[str, Any] = {}
        json_body: dict[str, Any] | None = None

        if location == "query":
            params[parameter] = value
        elif location == "json":
            json_body = {parameter: value}
        else:
            raise RuntimeError(
                "TENABLE_ANALYSIS_ID_LOCATION must be confirmed as "
                "'query' or 'json'."
            )

        payload = self._request_json(
            settings.tenable_analysis_method,
            settings.tenable_analysis_path,
            params=params or None,
            json_body=json_body,
        )

        return self._extract_records(
            payload,
            record_kind="finding",
        )

    def list_findings(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch and normalize detailed findings via the BRD routes."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        filters = filters or {}
        scans = self._fetch_all_scans()
        normalized_findings: list[dict[str, Any]] = []
        seen_source_ids: set[str] = set()

        for scan in scans:
            details = self._fetch_analysis(scan)

            for detail in details:
                # The scan ID belongs to the scan, not automatically to an
                # individual finding. Only use an identity present on detail.
                finding = normalize_tenable_record(
                    detail,
                    scan_metadata=scan,
                )

                source_id = finding.get("source_finding_id")
                if source_id is not None:
                    if source_id in seen_source_ids:
                        continue
                    seen_source_ids.add(source_id)

                severity_filter = filters.get("severity")
                if severity_filter:
                    if (
                        (finding.get("severity") or "").casefold()
                        != str(severity_filter).casefold()
                    ):
                        continue

                if filters.get("actionable_only"):
                    payload = finding.get("source_payload") or {}
                    metadata = payload.get("_brd_normalization") or {}

                    if metadata.get("actionable") is False:
                        continue

                ip_filter = filters.get("ip_address")
                if ip_filter and finding.get("ip_address") != ip_filter:
                    continue

                normalized_findings.append(finding)

                if len(normalized_findings) > self.settings.tenable_max_scan_results:
                    raise RuntimeError(
                        "Tenable detail import exceeded the configured "
                        "safety limit."
                    )

        return normalized_findings[offset : offset + limit]