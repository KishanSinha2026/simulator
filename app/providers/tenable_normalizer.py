"""Normalize Tenable scanner records according to VPM360 BRD Appendix A.

Preserves the complete received record and creates a normalized view of
all 54 BRD fields. This module does not assume that a specific Tenable
endpoint returns all 54 fields.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


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


# Field aliases accommodate differences in source JSON key naming.
# They do not assert that every endpoint returns every field.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "Plugin": ("Plugin", "plugin_id", "pluginID", "plugin"),
    "Plugin Name": ("Plugin Name", "plugin_name", "pluginName"),
    "Family": ("Family", "plugin_family", "pluginFamily", "family"),
    "Severity": ("Severity", "severity"),
    "IP Address": ("IP Address", "ip_address", "ipv4", "ip", "host_ip"),
    "Protocol": ("Protocol", "protocol"),
    "Port": ("Port", "port"),
    "Exploit?": (
        "Exploit?", "exploit_available", "exploit", "exploitAvailable"
    ),
    "Repository": ("Repository", "repository", "repository_name"),
    "MAC Address": ("MAC Address", "mac_address", "macAddress", "mac"),
    "DNS Name": ("DNS Name", "dns_name", "dnsName", "hostname"),
    "NetBIOS Name": ("NetBIOS Name", "netbios_name", "netbiosName"),
    "Plugin Output": ("Plugin Output", "plugin_output", "pluginOutput"),
    "Synopsis": ("Synopsis", "synopsis"),
    "Description": ("Description", "description"),
    "Steps to Remediate": (
        "Steps to Remediate", "steps_to_remediate", "solution", "remediation"
    ),
    "See Also": ("See Also", "see_also", "seeAlso"),
    "Risk Factor": ("Risk Factor", "risk_factor", "riskFactor"),
    "STIG Severity": ("STIG Severity", "stig_severity", "stigSeverity"),
    "Vulnerability Priority Rating": (
        "Vulnerability Priority Rating",
        "vuln_priority_rating",
        "vpr",
        "vulnerabilityPriorityRating",
    ),
    "Exploit Prediction Scoring System (EPSS)": (
        "Exploit Prediction Scoring System (EPSS)",
        "epss",
        "epss_score",
        "epssScore",
    ),
    "CVSS V2 Base Score": (
        "CVSS V2 Base Score", "cvss_v2_base_score",
        "cvss_base_score", "cvssBaseScore",
    ),
    "CVSS V3 Base Score": (
        "CVSS V3 Base Score", "cvss_v3_base_score",
        "cvss3_base_score", "cvss3BaseScore",
    ),
    "CVSS V4 Base Score": (
        "CVSS V4 Base Score", "cvss_v4_base_score",
        "cvss4_base_score", "cvss4BaseScore",
    ),
    "CVSS V2 Temporal Score": (
        "CVSS V2 Temporal Score", "cvss_v2_temporal_score",
        "cvss_temporal_score",
    ),
    "CVSS V3 Temporal Score": (
        "CVSS V3 Temporal Score", "cvss_v3_temporal_score",
        "cvss3_temporal_score",
    ),
    "CVSS V4 Threat Score": (
        "CVSS V4 Threat Score", "cvss_v4_threat_score",
        "cvss4_threat_score",
    ),
    "CVSS V2 Vector": ("CVSS V2 Vector", "cvss_v2_vector", "cvss_vector"),
    "CVSS V3 Vector": ("CVSS V3 Vector", "cvss_v3_vector", "cvss3_vector"),
    "CVSS V4 Vector": ("CVSS V4 Vector", "cvss_v4_vector", "cvss4_vector"),
    "CVSS V4 Threat Vector": (
        "CVSS V4 Threat Vector", "cvss_v4_threat_vector",
        "cvss4_threat_vector",
    ),
    "CVSS V4 Supplemental": (
        "CVSS V4 Supplemental", "cvss_v4_supplemental",
        "cvss4_supplemental",
    ),
    "CPE": ("CPE", "cpe", "cpes"),
    "CVE": ("CVE", "cve", "cve_ids", "cves"),
    "BID": ("BID", "bid", "bugtraq_id"),
    "Cross References": (
        "Cross References", "cross_references", "crossReferences",
        "xref", "xrefs",
    ),
    "First Discovered": (
        "First Discovered", "first_discovered", "first_seen", "firstSeen",
    ),
    "Last Observed": (
        "Last Observed", "last_observed", "last_seen", "lastSeen",
    ),
    "Vuln Publication Date": (
        "Vuln Publication Date", "vuln_publication_date",
        "vulnerability_publication_date",
    ),
    "Security End of Life Date": (
        "Security End of Life Date", "security_eol_date",
        "security_end_of_life_date",
    ),
    "Patch Publication Date": (
        "Patch Publication Date", "patch_publication_date",
    ),
    "Plugin Publication Date": (
        "Plugin Publication Date", "plugin_publication_date",
    ),
    "Plugin Modification Date": (
        "Plugin Modification Date", "plugin_modification_date",
        "plugin_modified_date",
    ),
    "Exploit Ease": ("Exploit Ease", "exploit_ease", "exploitEase"),
    "Exploit Frameworks": (
        "Exploit Frameworks", "exploit_frameworks", "exploitFrameworks",
    ),
    "Check Type": ("Check Type", "check_type", "checkType"),
    "Version": ("Version", "version", "plugin_version"),
    "Recast Risk Comment": (
        "Recast Risk Comment", "recast_risk_comment", "recastRiskComment",
    ),
    "Accept Risk Comment": (
        "Accept Risk Comment", "accept_risk_comment", "acceptRiskComment",
    ),
    "Agent ID": ("Agent ID", "agent_id", "agent_uuid", "agentID"),
    "Host ID": ("Host ID", "host_id", "host_uuid", "hostID"),
    "Nessus Web Tests": (
        "Nessus Web Tests", "nessus_web_tests", "web_tests",
    ),
    "Thorough Tests": (
        "Thorough Tests", "thorough_tests", "thoroughTests",
    ),
    "Scan Accuracy": ("Scan Accuracy", "scan_accuracy", "scanAccuracy"),
}


def _key(value: Any) -> str:
    """Canonicalize keys without modifying original source keys."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _lookup(record: dict[str, Any], aliases: Iterable[str]) -> Any:
    """Find a value through aliases while preserving its original value."""
    index = {_key(name): value for name, value in record.items()}

    for alias in aliases:
        normalized = _key(alias)
        if normalized in index:
            return index[normalized]

    return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip()

        if not cleaned or cleaned.upper() in {
            "N/A", "NA", "NONE", "NULL"
        }:
            return None

        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)

    if number is None or not number.is_integer():
        return None

    return int(number)


def _as_text(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        return value.strip() or None

    if isinstance(value, (int, float, bool)):
        return str(value)

    return None


def _as_datetime(value: Any) -> datetime | None:
    """Parse supported timestamps; never invent a date for invalid input."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, datetime):
        return value

    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value or value.upper() in {"N/A", "NA", "NONE", "NULL"}:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass

    # Support timezone labels used in the BRD's sample timestamps.
    offsets = {
        "EDT": -4, "EST": -5,
        "CDT": -5, "CST": -6,
        "MDT": -6, "MST": -7,
        "PDT": -7, "PST": -8,
    }

    match = re.match(
        r"^(.*)\s+(EDT|EST|CDT|CST|MDT|MST|PDT|PST)$",
        value,
        re.IGNORECASE,
    )

    if match:
        date_text = match.group(1)
        zone = match.group(2).upper()

        try:
            parsed = datetime.strptime(date_text, "%b %d, %Y %H:%M:%S")
            return parsed.replace(
                tzinfo=timezone(timedelta(hours=offsets[zone]))
            )
        except ValueError:
            pass

    for fmt in (
        "%b %d, %Y %H:%M:%S",
        "%b %d, %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def _as_cve_list(value: Any) -> list[str]:
    """Preserve every CVE identifier, including comma-separated identifiers."""
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        candidates = value
    elif isinstance(value, str):
        candidates = re.split(r"[,;\s]+", value.strip())
    else:
        candidates = [value]

    result: list[str] = []

    for candidate in candidates:
        if candidate is None:
            continue

        if isinstance(candidate, dict):
            candidate = (
                candidate.get("name")
                or candidate.get("cve")
                or candidate.get("id")
            )

        if not isinstance(candidate, str):
            continue

        cve = candidate.strip().upper()

        if (
            cve
            and cve not in {"N/A", "NA", "NONE", "NULL"}
            and cve not in result
        ):
            result.append(cve)

    return result


def normalize_tenable_record(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize one record into the current VPM360 Tenable shape.

    `source_payload` retains the source record and adds:
    - `_brd_54_fields`: all 54 exact BRD labels, with None for absent fields.
    - `_brd_normalization`: CVSS selection and workflow hints.

    Missing fields must be checked against the actual configured endpoint.
    """
    if not isinstance(item, dict):
        raise TypeError("Tenable source record must be a JSON object")

    brd_fields = {
        label: _lookup(item, _FIELD_ALIASES[label])
        for label in TENABLE_BRD_54_FIELDS
    }

    plugin_id = _as_int(brd_fields["Plugin"])
    plugin_name = _as_text(brd_fields["Plugin Name"])

    severity = _as_text(brd_fields["Severity"])
    normalized_severity = severity.strip().lower() if severity else None

    if normalized_severity == "info":
        normalized_severity = "informational"

    cvss_v3 = _as_float(brd_fields["CVSS V3 Base Score"])
    cvss_v4 = _as_float(brd_fields["CVSS V4 Base Score"])

    # BRD: use CVSS V3 first; CVSS V4 only if V3 is unavailable.
    normalized_cvss = cvss_v3 if cvss_v3 is not None else cvss_v4

    cve_ids = _as_cve_list(brd_fields["CVE"])

    # Use a real source finding ID if supplied; do not fake a unique ID
    # from plugin_id because one plugin can affect many hosts.
    source_finding_id = _lookup(
        item,
        (
            "source_finding_id",
            "finding_uuid",
            "finding_id",
            "vulnerability_id",
            "source_id",
        ),
    )

    if source_finding_id is not None:
        source_finding_id = str(source_finding_id).strip() or None

    # Keep original keys and values. Additional metadata does not overwrite
    # any source key except the two private metadata keys below.
    source_payload = dict(item)
    source_payload["_brd_54_fields"] = brd_fields
    source_payload["_brd_normalization"] = {
        "normalized_cvss_base_score": normalized_cvss,
        "cvss_base_score_source": (
            "CVSS V3 Base Score"
            if cvss_v3 is not None
            else "CVSS V4 Base Score"
            if cvss_v4 is not None
            else None
        ),
        "actionable": normalized_severity != "informational",
        "informational_exclusion_applied_to_source_record": False,
        "note": (
            "Informational records are retained here. Exclude them from "
            "actionable workflows at the workflow/query boundary."
        ),
    }

    return {
        "source_finding_id": source_finding_id,

        # The current database scan_id is an internal FK. Do not populate it
        # using an external scan ID without resolving the matching DB row.
        "scan_id": None,

        "plugin_id": plugin_id,
        "plugin_name": plugin_name,
        "ip_address": _as_text(brd_fields["IP Address"]),
        "dns_name": _as_text(brd_fields["DNS Name"]),
        "host_id": _as_text(brd_fields["Host ID"]),
        "severity": normalized_severity,
        "synopsis": _as_text(brd_fields["Synopsis"]),
        "description": _as_text(brd_fields["Description"]),
        "plugin_output": _as_text(brd_fields["Plugin Output"]),
        "steps_to_remediate": _as_text(
            brd_fields["Steps to Remediate"]
        ),
        "cvss_v3_base_score": cvss_v3,
        "cvss_v4_base_score": cvss_v4,
        "normalized_cvss_base_score": normalized_cvss,
        "first_discovered": _as_datetime(
            brd_fields["First Discovered"]
        ),
        "last_observed": _as_datetime(brd_fields["Last Observed"]),
        "repository": _as_text(brd_fields["Repository"]),
        "protocol": _as_text(brd_fields["Protocol"]),
        "port": _as_int(brd_fields["Port"]),
        "cve_ids": cve_ids,
        "source_payload": source_payload,
    }


def missing_brd_fields(item: dict[str, Any]) -> list[str]:
    """List BRD fields without a matching key in the received source record."""
    if not isinstance(item, dict):
        raise TypeError("Tenable source record must be a JSON object")

    return [
        label
        for label in TENABLE_BRD_54_FIELDS
        if _lookup(item, _FIELD_ALIASES[label]) is None
    ]