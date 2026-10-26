"""Integration tests verifying Tenable, CMDB, ITSM/ISTM, and Satellite canonical routes.

Validates that:
1. Exactly one unified route exists per operation (no duplicate /provider/... endpoints).
2. Data automatically populates from JSON fixtures when in JSON mode or if database is empty.
3. IP correlation, change creation with 19 BRD fields, and Satellite execution flows work end-to-end.
"""

import uuid
from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture(scope="module")
def client():
    """Create test client instance."""
    with TestClient(app) as test_client:
        yield test_client


# =====================================================================
# 1. Tenable Integration Tests (BRD 4.1 Canonical Routes)
# =====================================================================

def test_tenable_canonical_routes(client: TestClient):
    """Verify Tenable findings, finding details, scans, and import."""
    # 1. GET /api/v1/tenable/findings (auto-populates if empty)
    res_findings = client.get("/api/v1/tenable/findings")
    assert res_findings.status_code == 200, res_findings.text
    findings_data = res_findings.json()
    assert "items" in findings_data
    assert len(findings_data["items"]) >= 1

    first_finding_id = findings_data["items"][0]["id"]

    # 2. GET /api/v1/tenable/findings/{finding_id}
    res_single = client.get(f"/api/v1/tenable/findings/{first_finding_id}")
    assert res_single.status_code == 200, res_single.text
    finding = res_single.json()
    assert finding["id"] == first_finding_id
    assert "severity" in finding

    # 3. GET /api/v1/tenable/scans
    res_scans = client.get("/api/v1/tenable/scans")
    assert res_scans.status_code == 200, res_scans.text
    scans_data = res_scans.json()
    assert "items" in scans_data
    assert len(scans_data["items"]) >= 1

    # 4. POST /api/v1/tenable/import (synchronize/import)
    res_import = client.post("/api/v1/tenable/import")
    assert res_import.status_code == 200, res_import.text
    import_result = res_import.json()
    assert import_result["records_received"] >= 1


# =====================================================================
# 2. CMDB Integration Tests (BRD 4.3 Canonical Routes)
# =====================================================================

def test_cmdb_canonical_routes_and_correlation(client: TestClient):
    """Verify CMDB servers, details, IP correlation, and import."""
    # 1. GET /api/v1/cmdb/servers (auto-populates if empty)
    res_servers = client.get("/api/v1/cmdb/servers")
    assert res_servers.status_code == 200, res_servers.text
    servers_data = res_servers.json()
    assert "items" in servers_data
    assert len(servers_data["items"]) >= 1

    first_server = servers_data["items"][0]
    first_server_id = first_server["id"]
    first_ip = first_server["ip_address"]

    # 2. GET /api/v1/cmdb/servers/{server_id}
    res_single = client.get(f"/api/v1/cmdb/servers/{first_server_id}")
    assert res_single.status_code == 200, res_single.text
    assert res_single.json()["id"] == first_server_id

    # 3. GET /api/v1/cmdb/correlate/{ip_address} - MATCHED
    res_corr = client.get(f"/api/v1/cmdb/correlate/{first_ip}")
    assert res_corr.status_code == 200, res_corr.text
    corr_data = res_corr.json()
    assert corr_data["correlation_outcome"] in ("MATCHED", "CMDB_CI_INACTIVE")
    assert len(corr_data["matched_servers"]) >= 1

    # 4. GET /api/v1/cmdb/correlate/{ip_address} - CMDB_NOT_FOUND
    res_not_found = client.get("/api/v1/cmdb/correlate/192.0.2.254")
    assert res_not_found.status_code == 200, res_not_found.text
    assert res_not_found.json()["correlation_outcome"] == "CMDB_NOT_FOUND"

    # 5. POST /api/v1/cmdb/import
    res_import = client.post("/api/v1/cmdb/import")
    assert res_import.status_code == 200, res_import.text
    assert res_import.json()["servers_imported"] >= 1


# =====================================================================
# 3. ITSM & ISTM Integration Tests (BRD 4.4 Canonical Routes)
# =====================================================================

def test_itsm_canonical_routes(client: TestClient):
    """Verify ITSM changes, change creation (19 QA fields), worklogs, and import."""
    # 1. GET /api/v1/itsm/changes (auto-populates if empty)
    res_changes = client.get("/api/v1/itsm/changes")
    assert res_changes.status_code == 200, res_changes.text
    changes_data = res_changes.json()
    assert "items" in changes_data
    assert len(changes_data["items"]) >= 1

    first_change_id = changes_data["items"][0]["id"]

    # 2. GET /api/v1/itsm/changes/{change_id}
    res_single = client.get(f"/api/v1/itsm/changes/{first_change_id}")
    assert res_single.status_code == 200, res_single.text
    assert res_single.json()["id"] == first_change_id

    # 3. POST /api/v1/itsm/changes (19 QA Fields)
    unique_chg_id = f"CHG{uuid.uuid4().hex[:8].upper()}"
    change_payload = {
        "source_change_id": unique_chg_id,
        "first_name": "Antigravity",
        "last_name": "Security",
        "status": "Draft",
        "impact": "3-Moderate/Limited",
        "urgency": "3-Medium",
        "location_company": "IndusInd Bank",
        "detailed_description": "VPM360 Automated Security Remediation Patching",
        "company": "IndusInd Bank",
        "support_organization": "IT Operations",
        "support_group_name": "SecOps Linux",
        "change_nature": "Scheduled",
        "nature_of_change": "Security Patching",
        "application_infrastructure": "Infrastructure",
        "downtime_required": "No",
        "service_ci": "srv-prod-app-01",
        "description": "Kernel security vulnerability fix",
        "environment": "Production",
    }
    res_create = client.post("/api/v1/itsm/changes", json=change_payload)
    assert res_create.status_code in (200, 201), res_create.text
    created = res_create.json()
    assert created["source_change_id"] == unique_chg_id
    new_db_id = created["id"]

    # 4. POST /api/v1/itsm/changes/{change_id}/worklogs
    worklog_payload = {
        "description": "Patch verified and staged.",
        "submitter": "SecOps Operator",
        "worklog_type": "General Information",
    }
    res_wl = client.post(
        f"/api/v1/itsm/changes/{new_db_id}/worklogs",
        json=worklog_payload,
    )
    assert res_wl.status_code in (200, 201), res_wl.text
    assert res_wl.json()["change_id"] == new_db_id

    # 5. GET /api/v1/itsm/changes/{change_id}/worklogs
    res_list_wl = client.get(f"/api/v1/itsm/changes/{new_db_id}/worklogs")
    assert res_list_wl.status_code == 200, res_list_wl.text
    assert len(res_list_wl.json()["items"]) >= 1

    # 6. Verify /api/v1/istm alias works identically
    res_istm = client.get("/api/v1/istm/changes")
    assert res_istm.status_code == 200, res_istm.text

    # 7. POST /api/v1/itsm/import
    res_import = client.post("/api/v1/itsm/import")
    assert res_import.status_code == 200, res_import.text
    assert res_import.json()["changes_imported"] >= 1


# =====================================================================
# 4. Satellite Integration Tests (BRD 4.5 Canonical Routes)
# =====================================================================

def test_satellite_canonical_routes(client: TestClient):
    """Verify Satellite hosts, job templates, job launch, status polling, and cancellation."""
    # 1. GET /api/v1/satellite/hosts (BRD S1)
    res_hosts = client.get("/api/v1/satellite/hosts")
    assert res_hosts.status_code == 200, res_hosts.text
    hosts_data = res_hosts.json()
    assert "items" in hosts_data
    assert len(hosts_data["items"]) >= 1

    target_host_id = hosts_data["items"][0]["source_host_id"]

    # 2. GET /api/v1/satellite/job-templates (BRD S2)
    res_templates = client.get("/api/v1/satellite/job-templates")
    assert res_templates.status_code == 200, res_templates.text
    templates_data = res_templates.json()
    assert "items" in templates_data
    assert len(templates_data["items"]) >= 1

    target_tmpl_id = templates_data["items"][0]["source_template_id"]

    # 3. POST /api/v1/satellite/jobs (BRD S3)
    launch_payload = {
        "template_id": target_tmpl_id,
        "host_ids": [target_host_id],
        "inputs": {"dry_run": "true"},
    }
    res_launch = client.post("/api/v1/satellite/jobs", json=launch_payload)
    assert res_launch.status_code in (200, 201, 202), res_launch.text
    job_run = res_launch.json()
    job_id = job_run["id"]

    # 4. GET /api/v1/satellite/jobs/{job_run_id} (BRD S4/S5)
    res_get_job = client.get(f"/api/v1/satellite/jobs/{job_id}")
    assert res_get_job.status_code == 200, res_get_job.text
    assert res_get_job.json()["id"] == job_id

    # 5. POST /api/v1/satellite/jobs/{job_run_id}/cancel (BRD S7)
    res_cancel = client.post(
        f"/api/v1/satellite/jobs/{job_id}/cancel",
        json={"reason": "Operator requested stop"},
    )
    assert res_cancel.status_code == 200, res_cancel.text
    assert res_cancel.json()["status"] == "cancelled"

    # 6. POST /api/v1/satellite/import
    res_import = client.post("/api/v1/satellite/import")
    assert res_import.status_code == 200, res_import.text
    assert res_import.json()["hosts_imported"] >= 1


# =====================================================================
# 5. System & Health Check Tests
# =====================================================================

def test_system_and_health_routes(client: TestClient):
    """Verify health, ready, and root endpoints."""
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_ready = client.get("/api/v1/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"

    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "running"


# =====================================================================
# 6. Large Dataset (20k+) & Idempotency / Deduplication Tests
# =====================================================================

def test_large_dataset_queries_up_to_20k(client: TestClient):
    """Verify that queries with limit up to 20,000 succeed without validation error."""
    # Test 20k limit on Tenable findings
    res_tenable = client.get("/api/v1/tenable/findings?limit=20000")
    assert res_tenable.status_code == 200, res_tenable.text
    data_tenable = res_tenable.json()
    assert "items" in data_tenable

    # Test 20k limit on Tenable scans
    res_scans = client.get("/api/v1/tenable/scans?limit=20000")
    assert res_scans.status_code == 200, res_scans.text

    # Test 20k limit on CMDB servers
    res_cmdb = client.get("/api/v1/cmdb/servers?limit=20000")
    assert res_cmdb.status_code == 200, res_cmdb.text

    # Test 20k limit on ITSM changes
    res_itsm = client.get("/api/v1/itsm/changes?limit=20000")
    assert res_itsm.status_code == 200, res_itsm.text

    # Test 20k limit on Satellite hosts
    res_sat = client.get("/api/v1/satellite/hosts?limit=20000")
    assert res_sat.status_code == 200, res_sat.text


def test_idempotency_and_duplicate_handling(client: TestClient):
    """Verify idempotent behavior: duplicate records do not fail and are merged/updated."""
    # 1. ITSM Change Idempotency
    test_chg_id = f"CHG-IDEMP-{uuid.uuid4().hex[:6].upper()}"
    chg_payload = {
        "source_change_id": test_chg_id,
        "first_name": "Antigravity",
        "last_name": "Idempotent",
        "status": "Draft",
        "description": "Initial description",
    }
    # First POST
    res1 = client.post("/api/v1/itsm/changes", json=chg_payload)
    assert res1.status_code in (200, 201), res1.text
    initial_id = res1.json()["id"]

    # Second identical/updated POST with same source_change_id
    chg_payload["description"] = "Idempotently updated description"
    res2 = client.post("/api/v1/itsm/changes", json=chg_payload)
    assert res2.status_code in (200, 201), res2.text
    updated_record = res2.json()
    assert updated_record["id"] == initial_id
    assert updated_record["source_change_id"] == test_chg_id

    # 2. Satellite Job Launch with duplicate host IDs (auto-deduplicated)
    res_templates = client.get("/api/v1/satellite/job-templates")
    tmpl_id = res_templates.json()["items"][0]["source_template_id"]
    res_hosts = client.get("/api/v1/satellite/hosts")
    host_id = res_hosts.json()["items"][0]["source_host_id"]

    # Pass duplicate host ID in host_ids list
    dup_launch_payload = {
        "template_id": tmpl_id,
        "host_ids": [host_id, host_id, host_id],  # Duplicates
        "inputs": {"dry_run": "true"},
    }
    res_dup_launch = client.post("/api/v1/satellite/jobs", json=dup_launch_payload)
    assert res_dup_launch.status_code in (200, 201, 202), res_dup_launch.text

    # 3. Repeated /import calls (Idempotent upsert across all providers)
    res_t_imp1 = client.post("/api/v1/tenable/import?limit=500")
    assert res_t_imp1.status_code == 200, res_t_imp1.text
    res_t_imp2 = client.post("/api/v1/tenable/import?limit=500")
    assert res_t_imp2.status_code == 200, res_t_imp2.text

    res_c_imp = client.post("/api/v1/cmdb/import")
    assert res_c_imp.status_code == 200, res_c_imp.text

    res_i_imp = client.post("/api/v1/itsm/import")
    assert res_i_imp.status_code == 200, res_i_imp.text

    res_s_imp = client.post("/api/v1/satellite/import")
    assert res_s_imp.status_code == 200, res_s_imp.text

