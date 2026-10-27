"""BRD-aligned normalization for Tenable scanner records."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import re


TENABLE_BRD_54_FIELDS: tuple[str, ...] = (
    "Plugin",
    "Plugin Name",
    "Family",
    "Severity",
    "IP Address",
    "Protocol",
    "Port",
    "Exploit?",
    "Repository",
    "MAC Address",
    "DNS Name",
    "NetBIOS Name",
    "Plugin Output",
    "Synopsis",
    "Description",
    "Steps to Remediate",
    "See Also",
    "Risk Factor",
    "STIG Severity",
    "Vulnerability Priority Rating",
    "Exploit Prediction Scoring System (EPSS)",
    "CVSS V2 Base Score",
    "CVSS V3 Base Score",
    "CVSS V4 Base Score",
    "CVSS V2 Temporal Score",
    "CVSS V3 Temporal Score",
    "CVSS V4 Threat Score",
    "CVSS V2 Vector",
    "CVSS V3 Vector",
    "CVSS V4 Vector",
    "CVSS V4 Threat Vector",
    "CVSS V4 Supplemental",
    "CPE",
    "CVE",
    "BID",
    "Cross References",
    "First Discovered",
    "Last Observed",
    "Vuln Publication Date",
    "Security End of Life Date",
    "Patch Publication Date",
    "Plugin Publication Date",
    "Plugin Modification Date",
    "Exploit Ease",
    "Exploit Frameworks",
    "Check Type",
    "Version",
    "Recast Risk Comment",
    "Accept Risk Comment",
    "Agent ID",
    "Host ID",
    "Nessus Web Tests",
    "Thorough Tests",
    "Scan Accuracy",
)


def _key(value: Any) -> str:
    """Normalize field names for case- and punctuation-insensitive lookup."""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "Plugin": ("plugin_id", "pluginId", "pluginID", "Plugin ID"),
    "Plugin Name": ("plugin_name", "pluginName"),
    "Family": ("plugin_family", "pluginFamily"),
    "IP Address": ("ip_address", "ipAddress", "ip", "host_ip"),
    "MAC Address": ("mac_address", "macAddress", "mac"),
    "DNS Name": ("dns_name", "dnsName", "hostname", "host_name"),
    "NetBIOS Name": ("netbios_name", "netbiosName"),
    "Plugin Output": ("plugin_output", "pluginOutput"),
    "Steps to Remediate": (
        "steps_to_remediate",
        "stepsToRemediate",
        "solution",
        "remediation",
    ),
    "See Also": ("see_also", "seeAlso", "references", "urls"),
    "Vulnerability Priority Rating": (
        "vulnerability_priority_rating",
        "vpr",
        "vpr_score",
    ),
    "Exploit Prediction Scoring System (EPSS)": (
        "epss",
        "epss_score",
        "exploit_prediction_scoring_system",
    ),
    "CVSS V2 Base Score": (
        "cvss_v2_base_score",
        "cvss2_base_score",
        "cvss2BaseScore",
    ),
    "CVSS V3 Base Score": (
        "cvss_v3_base_score",
        "cvss3_base_score",
        "cvss3BaseScore",
    ),
    "CVSS V4 Base Score": (
        "cvss_v4_base_score",
        "cvss4_base_score",
        "cvss4BaseScore",
    ),
    "CVSS V2 Temporal Score": (
        "cvss_v2_temporal_score",
        "cvss2_temporal_score",
    ),
    "CVSS V3 Temporal Score": (
        "cvss_v3_temporal_score",
        "cvss3_temporal_score",
    ),
    "CVSS V4 Threat Score": (
        "cvss_v4_threat_score",
        "cvss4_threat_score",
    ),
    "CVSS V2 Vector": ("cvss_v2_vector", "cvss2_vector"),
    "CVSS V3 Vector": ("cvss_v3_vector", "cvss3_vector"),
    "CVSS V4 Vector": ("cvss_v4_vector", "cvss4_vector"),
    "CVSS V4 Threat Vector": (
        "cvss_v4_threat_vector",
        "cvss4_threat_vector",
    ),
    "CVSS V4 Supplemental": (
        "cvss_v4_supplemental",
        "cvss4_supplemental",
    ),
    "CPE": ("cpe", "cpes"),
    "CVE": ("cve", "cve_ids", "cveIds", "cves"),
    "BID": ("bid", "bugtraq_id", "bugtraq"),
    "Cross References": (
        "cross_references",
        "crossReferences",
        "xref",
    ),
    "First Discovered": (
        "first_discovered",
        "firstDiscovered",
        "first_seen",
        "first_seen_at",
    ),
    "Last Observed": (
        "last_observed",
        "lastObserved",
        "last_seen",
        "last_seen_at",
    ),
    "Vuln Publication Date": (
        "vuln_publication_date",
        "vulnerability_publication_date",
    ),
    "Security End of Life Date": (
        "security_end_of_life_date",
        "end_of_life_date",
    ),
    "Patch Publication Date": ("patch_publication_date",),
    "Plugin Publication Date": (
        "plugin_publication_date",
        "published",
    ),
    "Plugin Modification Date": (
        "plugin_modification_date",
        "modified",
    ),
    "Exploit?": ("exploit", "has_exploit", "exploit_available"),
    "Risk Factor": ("risk_factor", "riskFactor"),
    "STIG Severity": ("stig_severity", "stigSeverity"),
    "Exploit Ease": ("exploit_ease", "exploitEase"),
    "Exploit Frameworks": (
        "exploit_frameworks",
        "exploitFrameworks",
    ),
    "Check Type": ("check_type", "checkType"),
    "Recast Risk Comment": (
        "recast_risk_comment",
        "recastRiskComment",
    ),
    "Accept Risk Comment": (
        "accept_risk_comment",
        "acceptRiskComment",
    ),
    "Agent ID": ("agent_id", "agentId"),
    "Host ID": ("host_id", "hostId"),
    "Nessus Web Tests": (
        "nessus_web_tests",
        "nessusWebTests",
    ),
    "Thorough Tests": ("thorough_tests", "thoroughTests"),
    "Scan Accuracy": ("scan_accuracy", "scanAccuracy"),
}


def _lookup(
    record: dict[str, Any],
    field_name: str,
    *extra_sources: dict[str, Any],
) -> Any:
    """Find a source field using its exact label or known aliases."""
    candidates: list[dict[str, Any]] = [
        record,
        *extra_sources,
    ]

    nested = record.get("source_payload")
    if isinstance(nested, dict):
        candidates.append(nested)

    normalized_names = [_key(field_name)]
    normalized_names.extend(
        _key(alias)
        for alias in _FIELD_ALIASES.get(field_name, ())
    )

    for source in candidates:
        if not isinstance(source, dict):
            continue

        indexed = {
            _key(key): value
            for key, value in source.items()
        }

        for name in normalized_names:
            if name in indexed:
                return indexed[name]

    return None


def _text(value: Any) -> str | None:
    """Convert a source scalar to text without inventing a value."""
    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return None

    result = str(value).strip()
    return result or None


def _number(value: Any) -> float | None:
    """Convert a source numeric value where possible."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, str):
        value = value.strip()

    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)

    if number is None or not number.is_integer():
        return None

    return int(number)


def _datetime(value: Any) -> datetime | None:
    """Parse common Tenable timestamps, preserving timezone information."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, datetime):
        return value

    raw = str(value).strip()
    if not raw or raw.casefold() in {"n/a", "na", "none", "null"}:
        return None

    # The BRD examples include timezone abbreviations such as EDT.
    zone_offsets = {
        " EDT": "-04:00",
        " EST": "-05:00",
        " CDT": "-05:00",
        " CST": "-06:00",
        " MDT": "-06:00",
        " MST": "-07:00",
        " PDT": "-07:00",
        " PST": "-08:00",
        " UTC": "+00:00",
        " GMT": "+00:00",
    }

    parse_value = raw
    for abbreviation, offset in zone_offsets.items():
        if parse_value.upper().endswith(abbreviation):
            parse_value = parse_value[:-len(abbreviation)] + offset
            break

    iso_value = parse_value.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(iso_value)
    except ValueError:
        pass

    formats = (
        "%b %d, %Y %H:%M:%S %z",
        "%b %d %Y %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )

    for fmt in formats:
        try:
            return datetime.strptime(parse_value, fmt)
        except ValueError:
            continue

    return None


def _cves(value: Any) -> list[str]:
    """Return every CVE identifier without duplicates."""
    if value is None:
        return []

    if isinstance(value, dict):
        # Do not guess which arbitrary dictionary property contains CVEs.
        nested = value.get("cve") or value.get("CVE") or value.get("id")
        return _cves(nested)

    if isinstance(value, (list, tuple, set)):
        raw_values: list[str] = []
        for item in value:
            raw_values.extend(_cves(item))
        return list(dict.fromkeys(raw_values))

    raw = str(value).strip()
    if not raw:
        return []

    # Tenable field catalogue examples use comma-separated identifiers.
    parts = re.split(r"[,;\r\n]+", raw)
    output: list[str] = []

    for part in parts:
        candidate = part.strip().upper()
        if candidate and candidate not in output:
            output.append(candidate)

    return output


def _source_identity(record: dict[str, Any]) -> str | None:
    """Use an identifier present on the detailed source record."""
    for field in (
        "source_finding_id",
        "finding_id",
        "findingId",
        "result_id",
        "resultId",
        "vulnerability_id",
        "vulnerabilityId",
        "id",
        "uuid",
    ):
        value = record.get(field)

        if value is not None and str(value).strip():
            return str(value).strip()

    return None


def normalize_tenable_record(
    record: dict[str, Any],
    *,
    scan_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map one detailed source finding to the existing VPM360 model.

    All 54 BRD source labels are retained in source_payload under
    ``_brd_54_fields``. Missing values are explicit and listed under
    ``_brd_missing_fields``; the normalizer does not claim that a missing
    source value was retrieved.
    """
    if not isinstance(record, dict):
        raise TypeError("A Tenable source record must be a JSON object")

    snapshot: dict[str, Any] = {
        field: _lookup(record, field)
        for field in TENABLE_BRD_54_FIELDS
    }

    missing_fields = [
        field
        for field, value in snapshot.items()
        if value is None or value == ""
    ]

    plugin_raw = snapshot["Plugin"]
    plugin_id = _integer(plugin_raw)

    plugin_name = _text(snapshot["Plugin Name"])

    severity = (
        _text(snapshot["Severity"])
        or _text(snapshot["Risk Factor"])
    )

    cvss_v3 = _number(snapshot["CVSS V3 Base Score"])
    cvss_v4 = _number(snapshot["CVSS V4 Base Score"])

    # Mandatory BRD precedence: V3, otherwise V4. Never V2.
    if cvss_v3 is not None:
        normalized_cvss = cvss_v3
        normalized_cvss_source = "CVSS V3 Base Score"
    elif cvss_v4 is not None:
        normalized_cvss = cvss_v4
        normalized_cvss_source = "CVSS V4 Base Score"
    else:
        normalized_cvss = None
        normalized_cvss_source = None

    first_discovered = _datetime(snapshot["First Discovered"])
    last_observed = _datetime(snapshot["Last Observed"])

    ip_address = _text(snapshot["IP Address"])
    dns_name = _text(snapshot["DNS Name"])
    host_id = _text(snapshot["Host ID"])
    protocol = _text(snapshot["Protocol"])
    port = _integer(snapshot["Port"])

    severity_normalized = (severity or "").strip().casefold()
    actionable = severity_normalized not in {
        "info",
        "informational",
    }

    cve_ids = _cves(snapshot["CVE"])

    source_payload = {
        # Complete source input is retained, including fields not mapped
        # into dedicated columns in the existing database schema.
        "raw_record": record,
        "scan_metadata": scan_metadata,
        "_brd_54_fields": snapshot,
        "_brd_missing_fields": missing_fields,
        "_brd_normalization": {
            "actionable": actionable,
            "normalized_cvss_base_score": normalized_cvss,
            "normalized_cvss_source": normalized_cvss_source,
            "cvss_v2_used_as_fallback": False,
            "source_identity_present": bool(_source_identity(record)),
            "cve_count": len(cve_ids),
            "first_discovered_parsed": first_discovered is not None,
            "last_observed_parsed": last_observed is not None,
        },
    }

    return {
        "source_finding_id": _source_identity(record),
        "scan_id": None,
        "plugin_id": plugin_id,
        "plugin_name": plugin_name,
        "ip_address": ip_address,
        "dns_name": dns_name,
        "host_id": host_id,
        "severity": severity,
        "synopsis": _text(snapshot["Synopsis"]),
        "description": _text(snapshot["Description"]),
        "plugin_output": _text(snapshot["Plugin Output"]),
        "steps_to_remediate": _text(snapshot["Steps to Remediate"]),
        "cvss_v3_base_score": cvss_v3,
        "cvss_v4_base_score": cvss_v4,
        "first_discovered": first_discovered,
        "last_observed": last_observed,
        "repository": _text(snapshot["Repository"]),
        "protocol": protocol,
        "port": port,
        "cve_ids": cve_ids,
        "source_payload": source_payload,
    }


def missing_brd_fields(record: dict[str, Any]) -> list[str]:
    """Return BRD labels for which the record has no source value."""
    return [
        field
        for field in TENABLE_BRD_54_FIELDS
        if _lookup(field, field, record) in (None, "")
    ]