"""Integration tests verifying Tenable, CMDB, ITSM/ISTM, and Satellite routes.

Tests both JSON provider mode and PostgreSQL database operations.
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
# 1. Tenable Integration Tests (JSON Provider & DB CRUD)
# =====================================================================

def test_tenable_provider_scans_and_findings(client: TestClient):
    """Verify Tenable JSON provider endpoints."""
    # JSON Provider scans preview (returns list)
    response = client.get("/api/v1/tenable/provider/scans")
    assert response.status_code == 200, response.text
    scans = response.json()
    assert isinstance(scans, list)
    assert len(scans) >= 1
    assert "id" in scans[0] or "scan_id" in scans[0]

    # JSON Provider findings preview (returns list)
    response = client.get("/api/v1/tenable/provider/findings")
    assert response.status_code == 200, response.text
    findings = response.json()
    assert isinstance(findings, list)
    assert len(findings) >= 1


def test_tenable_import_and_db_endpoints(client: TestClient):
    """Verify Tenable provider-to-DB import and DB endpoints."""
    # Import from provider into DB
    response = client.post("/api/v1/tenable/provider/import")
    assert response.status_code == 200, response.text
    import_result = response.json()
    assert import_result["records_received"] >= 1

    # DB scans list
    response = client.get("/api/v1/tenable/scans")
    assert response.status_code == 200
    scans_data = response.json()
    assert "items" in scans_data
    assert len(scans_data["items"]) >= 1

    # DB findings list
    response = client.get("/api/v1/tenable/findings")
    assert response.status_code == 200
    findings_data = response.json()
    assert "items" in findings_data
    assert len(findings_data["items"]) >= 1

    # Create new scan directly in DB
    unique_scan_id = f"scan-{uuid.uuid4().hex[:6]}"
    new_scan = {
        "source_scan_id": unique_scan_id,
        "name": "Integration Test Scan",
        "status": "completed",
    }
    response = client.post("/api/v1/tenable/scans", json=new_scan)
    assert response.status_code in (200, 201), response.text
    created = response.json()
    assert created["source_scan_id"] == unique_scan_id


# =====================================================================
# 2. CMDB Integration Tests (JSON Provider, DB CRUD & IP Correlation)
# =====================================================================

def test_cmdb_provider_and_import(client: TestClient):
    """Verify CMDB provider endpoints and DB import."""
    # Provider endpoints (JSON fixtures return list)
    res_servers = client.get("/api/v1/cmdb/provider/servers")
    assert res_servers.status_code == 200
    servers = res_servers.json()
    assert isinstance(servers, list)
    assert len(servers) >= 1

    res_mw = client.get("/api/v1/cmdb/provider/middleware")
    assert res_mw.status_code == 200
    mw = res_mw.json()
    assert isinstance(mw, list)
    assert len(mw) >= 1

    res_db = client.get("/api/v1/cmdb/provider/databases")
    assert res_db.status_code == 200
    databases = res_db.json()
    assert isinstance(databases, list)
    assert len(databases) >= 1

    # Import into DB
    res_import = client.post("/api/v1/cmdb/provider/import")
    assert res_import.status_code == 200, res_import.text
    import_data = res_import.json()
    assert import_data["servers_imported"] >= 1
    assert import_data["middleware_imported"] >= 1
    assert import_data["databases_imported"] >= 1


def test_cmdb_db_endpoints_and_correlation(client: TestClient):
    """Verify CMDB DB CRUD and IP correlation matching BRD Section 4.3."""
    # Ensure provider data is imported into DB
    client.post("/api/v1/cmdb/provider/import")

    # DB listing
    res_servers = client.get("/api/v1/cmdb/servers")
    assert res_servers.status_code == 200
    servers = res_servers.json()["items"]
    assert len(servers) >= 1

    matched_ip = servers[0]["ip_address"]

    # IP Correlation - MATCHED outcome
    res_corr = client.get(f"/api/v1/cmdb/correlate/{matched_ip}")
    assert res_corr.status_code == 200
    corr_data = res_corr.json()
    assert corr_data["correlation_outcome"] in ("MATCHED", "CMDB_CI_INACTIVE")
    assert len(corr_data["matched_servers"]) >= 1

    # IP Correlation - CMDB_NOT_FOUND outcome
    res_not_found = client.get("/api/v1/cmdb/correlate/192.0.2.254")
    assert res_not_found.status_code == 200
    assert res_not_found.json()["correlation_outcome"] == "CMDB_NOT_FOUND"

    # Create server directly in DB
    unique_srv_id = f"SRV-TEST-{uuid.uuid4().hex[:6]}"
    new_server = {
        "source_instance_id": unique_srv_id,
        "ci_name": "srv-test-app-01",
        "dns_host_name": "srv-test-app-01.bank.local",
        "ip_address": "10.50.99.1",
        "production_status": "Active",
        "operating_system": "Red Hat Enterprise Linux 8.9",
        "risk_classification": "Medium",
    }
    res_create = client.post("/api/v1/cmdb/servers", json=new_server)
    assert res_create.status_code in (200, 201), res_create.text
    assert res_create.json()["ci_name"] == "srv-test-app-01"


# =====================================================================
# 3. ITSM & ISTM Integration Tests (Both path aliases supported)
# =====================================================================

def test_itsm_and_istm_provider_and_import(client: TestClient):
    """Verify both /api/v1/itsm and /api/v1/istm route aliases."""
    # Test /itsm/provider/changes (JSON provider returns list)
    res_itsm = client.get("/api/v1/itsm/provider/changes")
    assert res_itsm.status_code == 200
    changes = res_itsm.json()
    assert isinstance(changes, list)
    assert len(changes) >= 1

    # Test /istm/provider/changes (user requested ISTM alias)
    res_istm = client.get("/api/v1/istm/provider/changes")
    assert res_istm.status_code == 200
    changes_istm = res_istm.json()
    assert isinstance(changes_istm, list)
    assert len(changes_istm) >= 1

    # Import via ITSM endpoint into DB
    res_import = client.post("/api/v1/itsm/provider/import")
    assert res_import.status_code == 200, res_import.text
    assert res_import.json()["changes_imported"] >= 1

    # Verify both /itsm/changes and /istm/changes query the same DB records
    res_changes_itsm = client.get("/api/v1/itsm/changes")
    res_changes_istm = client.get("/api/v1/istm/changes")
    assert res_changes_itsm.status_code == 200
    assert res_changes_istm.status_code == 200
    assert len(res_changes_itsm.json()["items"]) == len(res_changes_istm.json()["items"])


def test_itsm_create_change_and_worklog(client: TestClient):
    """Verify creating ITSM change and worklog in DB."""
    unique_chg_id = f"CHG{uuid.uuid4().hex[:8].upper()}"
    change_payload = {
        "source_change_id": unique_chg_id,
        "description": "Emergency Security Kernel Patch",
        "first_name": "Antigravity",
        "last_name": "Security",
        "status": "Draft",
        "service_ci": "srv-prod-app-01",
        "environment": "Production",
    }
    res_create = client.post("/api/v1/itsm/changes", json=change_payload)
    assert res_create.status_code in (200, 201), res_create.text
    created_change = res_create.json()
    assert created_change["source_change_id"] == unique_chg_id
    db_change_id = created_change["id"]

    # Add worklog via /istm/changes/{change_id}/worklogs
    worklog_payload = {
        "description": "Patch verified in pre-prod simulator.",
        "submitter": "SecOps User",
        "worklog_type": "General Information",
    }
    res_wl = client.post(
        f"/api/v1/istm/changes/{db_change_id}/worklogs",
        json=worklog_payload,
    )
    assert res_wl.status_code in (200, 201), res_wl.text
    assert res_wl.json()["change_id"] == db_change_id


# =====================================================================
# 4. Satellite Integration Tests (JSON Provider, DB CRUD & Jobs)
# =====================================================================

def test_satellite_provider_and_import(client: TestClient):
    """Verify Satellite provider endpoints and DB import."""
    # Provider endpoints (JSON fixtures return list)
    res_hosts = client.get("/api/v1/satellite/provider/hosts")
    assert res_hosts.status_code == 200
    hosts = res_hosts.json()
    assert isinstance(hosts, list)
    assert len(hosts) >= 1

    res_templates = client.get("/api/v1/satellite/provider/job-templates")
    assert res_templates.status_code == 200
    templates = res_templates.json()
    assert isinstance(templates, list)
    assert len(templates) >= 1

    # Import into DB
    res_import = client.post("/api/v1/satellite/provider/import")
    assert res_import.status_code == 200, res_import.text
    import_data = res_import.json()
    assert import_data["hosts_imported"] >= 1
    assert import_data["job_templates_imported"] >= 1


def test_satellite_db_crud_and_job_execution(client: TestClient):
    """Verify Satellite DB hosts, template creation, job launch, and cancellation."""
    # Ensure provider data is imported into DB
    client.post("/api/v1/satellite/provider/import")

    # DB hosts
    res_hosts = client.get("/api/v1/satellite/hosts")
    assert res_hosts.status_code == 200
    hosts = res_hosts.json()["items"]
    assert len(hosts) >= 1

    source_host_id = hosts[0]["source_host_id"]

    # DB job templates
    res_templates = client.get("/api/v1/satellite/job-templates")
    assert res_templates.status_code == 200
    templates = res_templates.json()["items"]
    assert len(templates) >= 1
    source_tmpl_id = templates[0]["source_template_id"]

    # Create / Launch job run in DB
    job_payload = {
        "template_id": source_tmpl_id,
        "host_ids": [source_host_id],
        "inputs": {"dry_run": "true"},
    }
    res_job = client.post("/api/v1/satellite/jobs", json=job_payload)
    assert res_job.status_code in (200, 201, 202), res_job.text
    job_run = res_job.json()
    job_id = job_run["id"]

    # Cancel job run in DB
    res_cancel = client.post(
        f"/api/v1/satellite/jobs/{job_id}/cancel",
        json={"reason": "Operator requested cancellation"},
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"
