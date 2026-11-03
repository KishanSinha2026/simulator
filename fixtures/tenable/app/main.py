from datetime import datetime, timezone
from typing import Any
import hmac

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.security import APIKeyHeader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cmdb_main import router as cmdb_router
from app.config import settings
from app.db import TenableReadSessionLocal, WriteSessionLocal
from app.models import Finding, Scan

app = FastAPI(
    title="VPM360 APIs",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=[
        {"name": "Tenable", "description": "Tenable Security Center-compatible scan and finding APIs."},
        {"name": "CMDB", "description": "BMC CMDB-compatible login, lookup, graphwalk, and schema APIs."},
    ],
)
app.include_router(cmdb_router)

tenable_api_key_header = APIKeyHeader(
    name="x-apikey",
    scheme_name="TenableAccessSecret",
    description="Enter: accesskey=<TENABLE_ACCESS_KEY>; secretkey=<TENABLE_SECRET_KEY>",
    auto_error=False,
)

def authenticate_tenable_keys(x_apikeys: str | None = Depends(tenable_api_key_header)) -> str:
    """Authenticate Tenable-compatible requests with server-configured keys."""
    if not settings.tenable_access_key or not settings.tenable_secret_key:
        raise HTTPException(status_code=503, detail="Tenable access/secret keys are not configured")
    if not x_apikeys:
        raise HTTPException(status_code=401, detail="Missing x-apikey header")
    supplied = {}
    try:
        for part in x_apikeys.split(";"):
            if not part.strip():
                continue
            key, value = part.strip().split("=", 1)
            supplied[key.strip().lower()] = value.strip()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Malformed x-apikey header") from exc
    access_ok = hmac.compare_digest(supplied.get("accesskey", ""), settings.tenable_access_key)
    secret_ok = hmac.compare_digest(supplied.get("secretkey", ""), settings.tenable_secret_key)
    if not (access_ok and secret_ok):
        raise HTTPException(status_code=401, detail="Invalid Tenable access key or secret key")
    return x_apikeys

def forward_tenable(method: str, path: str, *, api_key: str, params: dict | None = None,
                    body: dict | None = None) -> Response:
    if not settings.tenable_source_url:
        raise HTTPException(status_code=503, detail="TENABLE_SOURCE_URL is required when DATA=API")
    url = settings.tenable_source_url.rstrip("/") + path
    try:
        upstream = httpx.request(method, url, headers={"x-apikey": api_key}, params=params,
                                 json=body, timeout=30.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the configured Tenable API") from exc
    status = upstream.status_code if upstream.status_code < 500 else 502
    return Response(content=upstream.content, status_code=status,
                    media_type=upstream.headers.get("content-type", "application/json"))

def ensure_tenable_db_configured() -> None:
    if not settings.database_url or "change-me" in settings.database_url:
        raise HTTPException(status_code=503, detail="Set DATABASE_URL in the server .env when DATA=DB")

def ensure_tenable_read_db_configured() -> None:
    if not settings.tenable_database_url or "change-me" in settings.tenable_database_url:
        raise HTTPException(status_code=503, detail="Set TENABLE_DATABASE_URL in the server .env when DATA=DB")

TENABLE_FINDING_FIELDS = [
    "Plugin", "Plugin Name", "Family", "Severity", "IP Address", "Protocol", "Port", "Exploit?",
    "Repository", "MAC Address", "DNS Name", "NetBIOS Name", "Plugin Output", "Synopsis", "Description",
    "Steps to Remediate", "See Also", "Risk Factor", "STIG Severity", "Vulnerability Priority Rating",
    "Exploit Prediction Scoring System (EPSS)", "CVSS V2 Base Score", "CVSS V3 Base Score", "CVSS V4 Base Score",
    "CVSS V2 Temporal Score", "CVSS V3 Temporal Score", "CVSS V4 Threat Score", "CVSS V2 Vector",
    "CVSS V3 Vector", "CVSS V4 Vector", "CVSS V4 Threat Vector", "CVSS V4 Supplemental", "CPE", "CVE",
    "BID", "Cross References", "First Discovered", "Last Observed", "Vuln Publication Date",
    "Security End of Life Date", "Patch Publication Date", "Plugin Publication Date", "Plugin Modification Date",
    "Exploit Ease", "Exploit Frameworks", "Check Type", "Version", "Recast Risk Comment",
    "Accept Risk Comment", "Agent ID", "Host ID", "Nessus Web Tests", "Thorough Tests", "Scan Accuracy",
]

FINDING_FIELD_SOURCES = {
    "Plugin": ("plugin_id",), "Plugin Name": ("plugin_name",), "Family": ("family",),
    "Severity": ("severity",), "IP Address": ("ip_address",), "Protocol": ("protocol",),
    "Port": ("port",), "Exploit?": ("exploit", "exploit_available"), "Repository": ("repository",),
    "MAC Address": ("mac_address",), "DNS Name": ("dns_name",), "NetBIOS Name": ("netbios_name",),
    "Plugin Output": ("plugin_output",), "Synopsis": ("synopsis",), "Description": ("description",),
    "Steps to Remediate": ("steps_to_remediate",), "See Also": ("see_also",),
    "Risk Factor": ("risk_factor", "severity"), "STIG Severity": ("stig_severity",),
    "Vulnerability Priority Rating": ("vulnerability_priority_rating",),
    "Exploit Prediction Scoring System (EPSS)": ("epss",),
    "CVSS V2 Base Score": ("cvss_v2_base_score",), "CVSS V3 Base Score": ("cvss_v3_base_score",),
    "CVSS V4 Base Score": ("cvss_v4_base_score",), "CVSS V2 Temporal Score": ("cvss_v2_temporal_score",),
    "CVSS V3 Temporal Score": ("cvss_v3_temporal_score",), "CVSS V4 Threat Score": ("cvss_v4_threat_score",),
    "CVSS V2 Vector": ("cvss_v2_vector",), "CVSS V3 Vector": ("cvss_v3_vector",),
    "CVSS V4 Vector": ("cvss_v4_vector",), "CVSS V4 Threat Vector": ("cvss_v4_threat_vector",),
    "CVSS V4 Supplemental": ("cvss_v4_supplemental",), "CPE": ("cpe",), "CVE": ("cve_ids", "cve"),
    "BID": ("bid",), "Cross References": ("cross_references",),
    "First Discovered": ("first_discovered",), "Last Observed": ("last_observed",),
    "Vuln Publication Date": ("vuln_publication_date",),
    "Security End of Life Date": ("security_end_of_life_date",),
    "Patch Publication Date": ("patch_publication_date",),
    "Plugin Publication Date": ("plugin_publication_date",),
    "Plugin Modification Date": ("plugin_modification_date",), "Exploit Ease": ("exploit_ease",),
    "Exploit Frameworks": ("exploit_frameworks",), "Check Type": ("check_type",), "Version": ("version",),
    "Recast Risk Comment": ("recast_risk_comment",), "Accept Risk Comment": ("accept_risk_comment",),
    "Agent ID": ("agent_id",), "Host ID": ("host_id",), "Nessus Web Tests": ("nessus_web_tests",),
    "Thorough Tests": ("thorough_tests",), "Scan Accuracy": ("scan_accuracy",),
}

SCAN_RESULT_FIELDS = {
    "id", "name", "description", "status", "initiator", "owner", "ownerGroup", "repository", "scan", "job",
    "details", "importStatus", "importStart", "importFinish", "importDuration", "downloadAvailable",
    "downloadFormat", "dataFormat", "resultType", "resultSource", "running", "errorDetails",
    "importErrorDetails", "totalIPs", "scannedIPs", "startTime", "finishTime", "scanDuration",
    "completedIPs", "completedChecks", "totalChecks", "agentScanUUID", "agentScanContainerUUID", "timeCompareField",
}

def epoch(value):
    return str(int(value.timestamp())) if value else "-1"

def scan_record(row: Scan, host_count: int = 0) -> dict[str, Any]:
    raw = row.raw_payload or {}
    details = {
        "id": str(row.id), "name": row.name or f"Fixture {row.id}",
        "description": row.description or "", "status": "Completed" if (row.status or "").lower() == "completed" else row.status,
        "initiator": {"id": "1", "username": "fixture-user", "firstname": "", "lastname": "", "uuid": ""},
        "owner": {"id": "1", "username": "fixture-user", "firstname": "", "lastname": "", "uuid": ""},
        "ownerGroup": {"id": "0", "name": "Full Access", "description": "Synthetic fixture access group"},
        "repository": {"id": "1", "name": row.repository or "Synthetic Fixture Repository", "description": "", "type": "Local", "dataFormat": "IPv4", "uuid": ""},
        "scan": {"id": str(row.id), "name": row.name or f"Fixture {row.id}", "description": row.description or "", "type": "policy"},
        "job": {"id": str(row.id), "name": row.name or f"Fixture {row.id}"},
        "details": "Synthetic scan result fixture; no hosts were scanned.", "importStatus": "Completed",
        "importStart": epoch(row.start_time), "importFinish": epoch(row.finish_time or row.start_time),
        "importDuration": "0", "downloadAvailable": "false", "downloadFormat": "v2", "dataFormat": "IPv4",
        "resultType": row.result_type or "active", "resultSource": "internal", "running": "false",
        "errorDetails": "", "importErrorDetails": "", "totalIPs": str(host_count),
        "scannedIPs": str(host_count), "startTime": epoch(row.start_time), "finishTime": epoch(row.finish_time or row.start_time),
        "scanDuration": str(row.scan_duration or 0), "completedIPs": str(host_count),
        "completedChecks": str(host_count * 6), "totalChecks": str(host_count * 6),
        "agentScanUUID": "", "agentScanContainerUUID": "", "timeCompareField": "createdTime",
    }
    # Preserve fields provided by a future real-shaped fixture, while keeping SC's public schema.
    for key in SCAN_RESULT_FIELDS:
        if key in raw and raw[key] is not None:
            details[key] = raw[key]
    return details

def finding_record(row: Finding) -> dict[str, Any]:
    raw = row.raw_payload or {}
    source = raw.get("source_payload") if isinstance(raw.get("source_payload"), dict) else {}
    values = {"plugin_id": row.plugin_id, "plugin_name": row.plugin_name, "family": row.family,
              "severity": row.severity, "ip_address": row.ip_address, "protocol": row.protocol,
              "port": row.port, "repository": row.repository, "dns_name": row.dns_name,
              "host_id": row.host_id, "plugin_output": row.plugin_output, "synopsis": row.synopsis,
              "description": row.description, "steps_to_remediate": row.steps_to_remediate,
              "cvss_v2_base_score": row.cvss_v2_base_score, "cvss_v3_base_score": row.cvss_v3_base_score,
              "cvss_v4_base_score": row.cvss_v4_base_score, "first_discovered": row.first_discovered,
              "last_observed": row.last_observed, "cve_ids": row.cve_ids,
              "exploit_available": row.exploit_available}
    result = {}
    for label in TENABLE_FINDING_FIELDS:
        aliases = FINDING_FIELD_SOURCES.get(label, ())
        value = raw.get(label)
        if value is None:
            value = next((values[key] for key in aliases if key in values and values[key] is not None), None)
        if value is None:
            value = next((source[key] for key in aliases if key in source and source[key] is not None), None)
        if label == "Exploit?" and value is not None:
            value = "Yes" if value is True or str(value).lower() in {"yes", "true", "1"} else "No"
        if label == "CVE" and isinstance(value, list):
            value = ",".join(value)
        result[label] = value
    return result

SEVERITY = {"info": (0, "Info"), "low": (1, "Low"), "medium": (2, "Medium"), "high": (3, "High"), "critical": (4, "Critical")}

def sc_finding_record(row: Finding) -> dict[str, Any]:
    raw = row.raw_payload or {}
    payload = raw.get("source_payload") if isinstance(raw.get("source_payload"), dict) else {}
    severity_id, severity_name = SEVERITY.get((row.severity or "info").lower(), (0, "Info"))
    cves = row.cve_ids or []
    cve_string = ",".join(cves)
    mac = raw.get("MAC Address") or payload.get("mac_address", "")
    netbios = raw.get("NetBIOS Name") or payload.get("netbios_name", "")
    first_seen = epoch(row.first_discovered)
    last_seen = epoch(row.last_observed)
    repo_name = row.repository or "Synthetic Fixture Repository"
    row_out = {
        "pluginID": str(row.plugin_id or ""),
        "severity": {"id": str(severity_id), "name": severity_name, "description": f"{severity_name} Severity"},
        "hasBeenMitigated": "1" if (row.status or "").lower() in {"closed", "fixed", "patched"} else "0",
        "acceptRisk": "0", "recastRisk": "0",
        "vprContext": raw.get("vprContext", "[]"), "epssScore": str(raw.get("epssScore", "")),
        "ip": row.ip_address or "", "ips": row.ip_address or "", "uuid": str(payload.get("agent_id", "")),
        "port": str(row.port or 0), "protocol": (row.protocol or "").upper(),
        "name": row.plugin_name or "", "pluginName": row.plugin_name or "", "dnsName": row.dns_name or "",
        "macAddress": mac, "netbiosName": netbios, "uniqueness": "repositoryID,hostUUID",
        "hostUniqueness": "repositoryID,hostUUID", "vulnUniqueness": "repositoryID,vulnUUID",
        "family": {"id": str(raw.get("familyID", "9999")), "name": row.family or "", "type": "active"},
        "repository": {"id": str(raw.get("repositoryID", "1")), "name": repo_name, "description": "", "dataFormat": "IPv4"},
        "pluginInfo": f"{row.plugin_id or ''} ({row.port or 0}/{(row.protocol or '').upper()}) {row.plugin_name or ''}".strip(),
        "firstSeen": first_seen, "lastSeen": last_seen,
        "exploitAvailable": "Yes" if row.exploit_available else "No",
        "exploitEase": raw.get("Exploit Ease", ""), "exploitFrameworks": raw.get("Exploit Frameworks", ""),
        "synopsis": row.synopsis or "", "description": row.description or "", "solution": row.steps_to_remediate or "",
        "seeAlso": raw.get("See Also", ""), "riskFactor": raw.get("Risk Factor", severity_name),
        "stigSeverity": raw.get("STIG Severity", ""), "vprScore": str(raw.get("Vulnerability Priority Rating", raw.get("vprScore", ""))),
        "baseScore": str(raw.get("CVSS V2 Base Score", "")), "temporalScore": str(raw.get("CVSS V2 Temporal Score", "")),
        "cvssVector": raw.get("CVSS V2 Vector", ""),
        "cvssV3BaseScore": str(row.cvss_v3_base_score) if row.cvss_v3_base_score is not None else "",
        "cvssV3TemporalScore": raw.get("CVSS V3 Temporal Score", ""), "cvssV3Vector": raw.get("CVSS V3 Vector", ""),
        "cvssV4BaseScore": str(row.cvss_v4_base_score) if row.cvss_v4_base_score is not None else "",
        "cvssV4Vector": raw.get("CVSS V4 Vector", ""), "cvssV4ThreatScore": raw.get("CVSS V4 Threat Score", ""),
        "cvssV4ThreatVector": raw.get("CVSS V4 Threat Vector", ""), "cvssV4Supplemental": raw.get("CVSS V4 Supplemental", ""),
        "cpe": raw.get("CPE", ""), "cve": cve_string, "bid": raw.get("BID", ""),
        "xref": raw.get("Cross References", ""), "vulnPubDate": raw.get("Vuln Publication Date", "-1"),
        "patchPubDate": raw.get("Patch Publication Date", "-1"),
        "pluginPubDate": raw.get("Plugin Publication Date", "-1"),
        "pluginModDate": raw.get("Plugin Modification Date", "-1"),
        "seolDate": raw.get("Security End of Life Date", "-1"), "pluginText": row.plugin_output or "",
        "operatingSystem": payload.get("operating_system", ""),
        "recastRiskRuleComment": raw.get("Recast Risk Comment", "N/A"),
        "acceptRiskRuleComment": raw.get("Accept Risk Comment", "N/A"),
        "hostUUID": row.host_id or "", "vulnUUID": row.source_finding_id,
        "cgiScanEnabled": raw.get("Nessus Web Tests", "Disabled"),
        "thoroughScanEnabled": raw.get("Thorough Tests", "Disabled"),
        "paranoidScanEnabled": raw.get("Scan Accuracy", "Not Paranoid"),
        "attachment": "", "brdFields": finding_record(row),
    }
    return row_out

@app.get("/rest/scanResult", tags=["Tenable"])
def scan_results(
    api_key: str = Depends(authenticate_tenable_keys),
    fields: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    if settings.data == "API":
        params = {key: value for key, value in {"fields": fields, "limit": limit, "offset": offset}.items()
                  if value is not None}
        return forward_tenable("GET", "/rest/scanResult", api_key=api_key, params=params)
    ensure_tenable_read_db_configured()
    now = int(datetime.now(timezone.utc).timestamp())
    if limit < 1 or limit > 10000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 10000")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be non-negative")
    statement = select(Scan)
    with TenableReadSessionLocal() as db:
        rows = db.scalars(statement.order_by(Scan.start_time.desc().nullslast()).offset(offset).limit(limit)).all()
        host_counts = dict(db.execute(select(Finding.scan_id, func.count(func.distinct(Finding.ip_address)))
                                      .group_by(Finding.scan_id)).all())
    items = [scan_record(row, host_counts.get(row.id, 0)) for row in rows]
    if fields:
        aliases = {"finishtime": "finishTime", "scanduration": "scanDuration"}
        selected = {aliases.get(field.strip(), field.strip()) for field in fields.split(",")}
        invalid = selected - SCAN_RESULT_FIELDS
        if invalid:
            raise HTTPException(status_code=400, detail=f"Unsupported scanResult fields: {', '.join(sorted(invalid))}")
        items = [{key: value for key, value in item.items() if key in selected} for item in items]
    return {"type": "regular", "response": {"usable": items, "manageable": items},
            "error_code": 0, "error_msg": "", "warnings": [], "timestamp": now}

@app.post("/rest/analysis", tags=["Tenable"])
def finding_analysis(query: dict[str, Any] | None = None, api_key: str = Depends(authenticate_tenable_keys)):
    """Implement the Security Center vuln analysis request and response envelope over fixture DB rows."""
    body = query or {}
    if settings.data == "API":
        return forward_tenable("POST", "/rest/analysis", api_key=api_key, body=body)
    ensure_tenable_db_configured()
    if body.get("type") != "vuln":
        raise HTTPException(status_code=400, detail="type must be 'vuln'")
    source_type = body.get("sourceType")
    if source_type not in {"cumulative", "patched", "individual"}:
        raise HTTPException(status_code=400, detail="sourceType must be cumulative, patched, or individual")
    query_def = body.get("query")
    if not isinstance(query_def, dict) or not query_def:
        raise HTTPException(status_code=400, detail="query must be a Tenable Security Center query object")
    tool = query_def.get("tool", "vulndetails")
    if tool not in {"vulndetails", "listvuln"}:
        raise HTTPException(status_code=400, detail="Supported analysis tools are vulndetails and listvuln")
    if source_type == "individual" and ("scanID" not in body or body.get("view") not in {"all", "new", "patched"}):
        raise HTTPException(status_code=400, detail="individual sourceType requires scanID and view")
    start_offset = int(body.get("startOffset", query_def.get("startOffset", 0)))
    end_offset = int(body.get("endOffset", query_def.get("endOffset", start_offset + 2000)))
    if start_offset < 0 or end_offset <= start_offset:
        raise HTTPException(status_code=400, detail="endOffset must be greater than startOffset")
    if end_offset - start_offset > 10000:
        raise HTTPException(status_code=400, detail="Tenable SC-compatible maximum page size is 10000")

    statement = select(Finding)
    count_statement = select(func.count()).select_from(Finding)
    conditions = []
    if source_type == "patched":
        conditions.append(func.lower(Finding.status).in_(["patched", "fixed", "closed"]))
    elif source_type == "cumulative":
        conditions.append(func.lower(Finding.status).notin_(["patched", "fixed", "closed"]))
    elif source_type == "individual":
        conditions.append(Finding.scan_id == str(body["scanID"]))
        if body["view"] == "patched":
            conditions.append(func.lower(Finding.status).in_(["patched", "fixed", "closed"]))
        elif body["view"] == "new":
            conditions.append(func.lower(Finding.status) == "new")
    filter_specs = query_def.get("filters", [])
    if not isinstance(filter_specs, list):
        raise HTTPException(status_code=400, detail="query.filters must be an array")
    severity_ids = {0: "info", 1: "low", 2: "medium", 3: "high", 4: "critical"}
    supported_filters = {"severity", "pluginID", "ip", "dnsName", "port", "protocol", "pluginName",
                         "exploitAvailable", "wasVuln", "repository", "cveID"}
    for spec in filter_specs:
        if not isinstance(spec, dict) or "filterName" not in spec:
            raise HTTPException(status_code=400, detail="Each filter requires filterName, operator, and value")
        name = spec["filterName"]
        value = spec.get("value")
        operator = spec.get("operator", "=")
        if name not in supported_filters:
            raise HTTPException(status_code=400, detail=f"Unsupported fixture filter: {name}")
        if operator not in {"=", "~"}:
            raise HTTPException(status_code=400, detail=f"Unsupported operator for {name}: {operator}")
        text_values = [v.strip() for v in str(value).split(",")] if not isinstance(value, dict) else []
        if name == "severity":
            names = [severity_ids.get(int(v), v.lower()) if v.isdigit() else v.lower() for v in text_values]
            conditions.append(func.lower(Finding.severity).in_(names))
        elif name == "pluginID":
            ids = [int(v) for v in text_values]
            conditions.append(Finding.plugin_id.in_(ids))
        elif name == "ip":
            conditions.append(Finding.ip_address.in_(text_values) if operator == "=" else Finding.ip_address.ilike(f"%{value}%"))
        elif name == "dnsName":
            conditions.append(Finding.dns_name.in_(text_values) if operator == "=" else Finding.dns_name.ilike(f"%{value}%"))
        elif name == "port":
            conditions.append(Finding.port.in_([int(v) for v in text_values]))
        elif name == "protocol":
            conditions.append(func.lower(Finding.protocol).in_([v.lower() for v in text_values]))
        elif name == "pluginName":
            conditions.append(Finding.plugin_name.ilike(f"%{value}%"))
        elif name == "exploitAvailable":
            conditions.append(Finding.exploit_available == (str(value).lower() in {"yes", "true", "1"}))
        elif name == "wasVuln":
            if value == "onlyWas":
                conditions.append(False)
            # Synthetic Nessus records are regular vulnerability records, never WAS records.
        elif name == "repository":
            repository_value = value.get("name", "") if isinstance(value, dict) else str(value)
            conditions.append(Finding.repository == repository_value)
        elif name == "cveID":
            cve_values = text_values
            for cve in cve_values:
                conditions.append(Finding.cve_ids.any(cve))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    with WriteSessionLocal() as db:
        total = db.scalar(count_statement) or 0
        rows = db.scalars(statement.order_by(Finding.last_observed.desc().nullslast())
                          .offset(start_offset).limit(end_offset - start_offset)).all()
    now = int(datetime.now(timezone.utc).timestamp())
    response = {"totalRecords": str(total), "returnedRecords": len(rows),
                "startOffset": str(start_offset), "endOffset": str(end_offset),
                "matchingDataElementCount": "-1", "results": [sc_finding_record(row) for row in rows]}
    return {"type": "regular", "response": response, "error_code": 0,
            "error_msg": "", "warnings": [], "timestamp": now}

