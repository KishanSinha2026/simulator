# VPM360 Integration Simulator

Enterprise vulnerability management and remediation integration simulator for **IndusInd Bank VPM360**, mapping the workflows in **BRD, HLD & TDD Section 4**. Vendor contracts and production-specific controls that the BRD leaves pending remain subject to client confirmation.

The simulator provides unified integration endpoints for **Tenable**, **BMC Helix CMDB**, **BMC Helix ITSM**, **Red Hat Satellite**, **Squad1**, **Microsoft SCCM 2509**, and **Ansible Automation Platform (AAP/AWX)**. Integrations can use configured vendor APIs or local PostgreSQL / JSON fixtures; a public workflow route may still be simulated when execution controls or client API contracts are pending.

Ansible Automation Platform / AWX is available as an API-backed patch execution integration. Configure `ANSIBLE_PROVIDER=api`, `ANSIBLE_BASE_URL`, and `ANSIBLE_API_KEY` in the environment (never commit the key). The API prefix defaults to `/api/controller/v2` for current AAP; set `ANSIBLE_API_PREFIX=/api/v2` for AWX/older controller deployments. `GET /api/v1/ansible/connection` checks API connectivity and authentication without launching a job. Other routes under `/api/v1/ansible` list job templates, launch jobs, refresh job status, and request cancellation. Launching a job can execute changes on selected hosts; restrict the API and controller template permissions accordingly. Job history is stored in `ansible_job_runs`; apply the Alembic migration before use.

---

## Table of Contents

1. [Architectural Overview](#architectural-overview)
2. [Data Schemas and JSON Formats](#data-schemas-and-json-formats)
   - [2.1 Tenable Vulnerability Management](#21-tenable-vulnerability-management)
   - [2.2 BMC Helix CMDB](#22-bmc-helix-cmdb)
   - [2.3 BMC Helix ITSM](#23-bmc-helix-itsm)
   - [2.4 Red Hat Satellite](#24-red-hat-satellite)
   - [2.5 Squad1 Vulnerability Management & Exception Handling](#25-squad1-vulnerability-management--exception-handling)
   - [2.6 Microsoft SCCM 2509 Enterprise Patch Management](#26-microsoft-sccm-2509-enterprise-patch-management)
   - [2.7 Ansible Automation Platform / AWX](#27-ansible-automation-platform--awx)
3. [Canonical BRD Route Catalog](#canonical-brd-route-catalog)
4. [20k+ Dataset Throughput & Idempotency](#20k-dataset-throughput--idempotency)
5. [Fixture Directory Structure](#fixture-directory-structure)
6. [Getting Started & Quickstart](#getting-started--quickstart)
   - [Environment Configuration](#environment-configuration)
   - [Database Setup & Migrations](#database-setup--migrations)
   - [Running the Application](#running-the-application)
   - [Running the Test Suite](#running-the-test-suite)

---

## Architectural Overview

- **Single-Route Architecture**: Callers invoke one VPM360 endpoint (e.g. `/api/v1/tenable/findings`) for the supported workflow. Depending on the integration and configured provider, an operation may use an external API, local PostgreSQL, or JSON fixtures. BRD-pending vendor operations are not treated as live integrations until the client confirms their contracts.
- **Auto-Synchronization**: Automatically imports and initializes baseline records from fixtures or remote sources into PostgreSQL if target tables are empty.
- **High-Performance Caching & Batch Ingestion**: File-modification (`st_mtime`) validated cache prevents re-parsing large JSON records on repeated calls. Ingestion batches in 500-item chunks with atomic commits.
- **Strict Idempotency**: Duplicate POST requests or repeated `/import` triggers merge updates smoothly based on natural source keys (`source_finding_id`, `source_instance_id`, `source_change_id`, `source_host_id`, `source_template_id`, `vulnerability_no`, `source_device_id`) rather than throwing HTTP 409, 422, or 500 errors.
- **Lightweight Sample Records for Squad1 & SCCM**: Baseline sample records (~3-5 records) are configured for Squad1 and SCCM 2509, allowing operators to load full 20k+ volume records after system verification.

---

## Data Schemas and JSON Formats

### 1. General Conventions

| Property | Rule |
|---|---|
| **JSON Root** | Fixture files are formatted as a JSON array (`[...]`) of record objects. |
| **Primary Keys** | `id` represents the internal database or fixture ID (integer in DB API responses, string in fixtures). |
| **Source Keys** | `source_*_id` stores canonical vendor identities and acts as the unique idempotency key. |
| **Timestamps** | ISO 8601 strings with timezone offset, e.g. `"2026-10-25T09:15:00Z"`. |
| **Payload Passthrough** | `source_payload` preserves un-normalized raw vendor fields without schema loss. |
| **Pagination Limits** | All listing endpoints support pagination up to `limit=50000` (`limit: int = Field(ge=1, le=50000)`). |

---

### 2.1 Tenable Vulnerability Management

#### Data Schema: Vulnerability Finding (`tenable_findings`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database identity (auto-generated) or fixture ID. |
| `source_finding_id` | string | No | Unique vendor finding identity (max 150 chars). Used for deduplication. |
| `scan_id` | integer \| `null` | No | Foreign key linking to `tenable_scans.id`. |
| `plugin_id` | integer | **Yes** | Tenable plugin ID (must be > 0). |
| `plugin_name` | string | **Yes** | Vulnerability / plugin title (1–500 chars). |
| `ip_address` | string \| `null` | No | Target IP address (IPv4/IPv6, max 45 chars). |
| `dns_name` | string \| `null` | No | Target FQDN / hostname (max 255 chars). |
| `host_id` | string \| `null` | No | Vendor host UUID / asset identifier. |
| `severity` | string \| `null` | No | Severity level (`info`, `low`, `medium`, `high`, `critical`). |
| `synopsis` | string \| `null` | No | Brief technical summary. |
| `description` | string \| `null` | No | Detailed vulnerability explanation. |
| `plugin_output` | string \| `null` | No | Scanner execution output text. |
| `steps_to_remediate`| string \| `null` | No | Guidance on how to patch or mitigate. |
| `cvss_v3_base_score`| number \| `null` | No | Float between 0.0 and 10.0. |
| `cvss_v4_base_score`| number \| `null` | No | Float between 0.0 and 10.0. |
| `first_discovered` | date-time string | No | ISO 8601 discovery timestamp. |
| `last_observed` | date-time string | No | ISO 8601 observation timestamp. |
| `repository` | string \| `null` | No | Repository or network compartment (max 255 chars). |
| `protocol` | string \| `null` | No | Network protocol (e.g. `tcp`, `udp`). |
| `port` | integer \| `null` | No | Network port (0–65535). |
| `cve_ids` | array of strings | No | List of associated CVE identifiers (e.g. `["CVE-2024-0001"]`). |
| `source_payload` | object \| `null` | No | Raw vendor response payload. |

#### Finding POST Payload (`POST /api/v1/tenable/findings`)
```json
{
  "source_finding_id": "tnb-finding-002",
  "plugin_id": 10107,
  "plugin_name": "SSH Protocol Version 1 Enabled",
  "ip_address": "192.0.2.20",
  "dns_name": "server02.example.local",
  "host_id": "host-002",
  "severity": "high",
  "synopsis": "The remote SSH service supports an outdated protocol version.",
  "description": "SSH protocol version 1 has known security weaknesses.",
  "plugin_output": "SSH protocol version 1 is enabled.",
  "steps_to_remediate": "Disable SSH protocol version 1 and configure SSH protocol version 2 only.",
  "cvss_v3_base_score": 7.5,
  "cvss_v4_base_score": null,
  "first_discovered": "2026-10-21T10:00:00Z",
  "last_observed": "2026-10-25T09:15:00Z",
  "repository": "Local Network",
  "protocol": "tcp",
  "port": 22,
  "cve_ids": ["CVE-2001-0144"]
}
```

Finding responses expose both the normalized `cves` relation records and the BRD-compatible `cve_ids` string array.

---

### 2.2 BMC Helix CMDB

#### Data Schema: Server Configuration Item (`cmdb_servers`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database or fixture ID. |
| `source_instance_id` | string | **Yes** | CMDB InstanceId (e.g. `OI-12345ABC`, max 100 chars). |
| `ci_name` | string \| `null` | No | Hostname or CI label (max 255 chars). |
| `dns_host_name` | string \| `null` | No | Fully qualified DNS domain name. |
| `ip_address` | string \| `null` | No | Primary IPv4/IPv6 address. |
| `application_name` | string \| `null` | No | Associated business application. |
| `asset_owner` | string \| `null` | No | Infrastructure asset owner. |
| `it_application_owner`| string \| `null` | No | Application team owner. |
| `system_environment` | string \| `null` | No | Environment stage (`Production`, `UAT`, `DR`). |
| `production_status` | string \| `null` | No | `Production`, `Non-Production`, etc. |
| `os_type` | string \| `null` | No | Operating system family (e.g. `Red Hat Enterprise Linux`, `Windows Server`). |
| `os_version` | string \| `null` | No | OS release version (e.g. `9.8`, `2022`). |
| `location` | string \| `null` | No | Physical or cloud data center location. |
| `status` | string \| `null` | No | Operational status (`Active`, `Inactive`, `Decommissioned`). |
| `source_payload` | object \| `null` | No | Un-normalized vendor attributes. |

#### CI Creation Payload (`POST /api/v1/cmdb/servers`)
```json
{
  "source_instance_id": "CI-SERVER-001",
  "ci_name": "srv-prod-app-01",
  "dns_host_name": "srv-prod-app-01.indusind.local",
  "ip_address": "192.0.2.10",
  "application_name": "Core Banking Portal",
  "asset_owner": "Enterprise Infrastructure Team",
  "it_application_owner": "SecOps Linux",
  "system_environment": "Production",
  "production_status": "Production",
  "os_type": "Red Hat Enterprise Linux",
  "os_version": "9.4",
  "location": "Mumbai DC",
  "status": "Active"
}
```

#### IP Correlation Output (`GET /api/v1/cmdb/correlate/{ip_address}` or `GET /api/v1/cmdb/correlate?ip_address=...`)
```json
{
  "ip_address": "192.0.2.10",
  "correlation_outcome": "MATCHED",
  "matched_servers": [
    {
      "id": 1,
      "source_instance_id": "CI-SERVER-001",
      "ci_name": "srv-prod-app-01",
      "ip_address": "192.0.2.10",
      "status": "Active"
    }
  ],
  "message": "Eligible server CI correlated successfully."
}
```

---

### 2.3 BMC Helix ITSM

#### Data Schema: Change Request (`itsm_changes`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database or fixture ID. |
| `source_change_id` | string | **Yes** | BMC Remedy change number (e.g. `CHG000000100001`). |
| `first_name` | string \| `null` | No | Submitter first name (max 100 chars). |
| `last_name` | string \| `null` | No | Submitter last name (max 100 chars). |
| `status` | string \| `null` | No | Lifecycle stage (`Draft`, `Request For Authorization`, `Scheduled`, `Completed`). |
| `impact` | string \| `null` | No | Impact code (e.g. `2000`, `3-Moderate/Limited`). |
| `urgency` | string \| `null` | No | Urgency code (e.g. `4000`, `3-Medium`). |
| `location_company` | string \| `null` | No | Site location company. |
| `company` | string \| `null` | No | Operating company name (`IndusInd Bank`). |
| `support_organization` | string \| `null` | No | Change coordinator organization. |
| `support_group_name` | string \| `null` | No | Assignee support group (e.g. `SecOps Linux`). |
| `change_nature` | string \| `null` | No | `Security Patch`, `Scheduled`, etc. |
| `nature_of_change` | string \| `null` | No | `Operating System Update`, `Security Patching`. |
| `application_infrastructure` | string \| `null` | No | `Infrastructure` or `Application`. |
| `downtime_required` | string \| `null` | No | `No`, `Yes`, `Pending Approval`. |
| `service_ci` | string \| `null` | No | Impacted Configuration Item label. |
| `description` | string \| `null` | No | Change title / summary text. |
| `detailed_description` | string \| `null` | No | Detailed change implementation plan. |
| `environment` | string \| `null` | No | Operating environment (`Production`, `UAT`). |
| `scheduled_start_at` | date-time string | No | Planned change execution window start. |
| `scheduled_end_at` | date-time string | No | Planned change execution window end. |
| `source_payload` | object \| `null` | No | Full unmapped vendor payload. |

#### Change Request POST Payload (`POST /api/v1/itsm/changes`)
```json
{
  "source_change_id": "CHG000000100001",
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
  "scheduled_start_at": "2026-11-02T20:00:00Z",
  "scheduled_end_at": "2026-11-02T22:00:00Z"
}
```

---

### 2.4 Red Hat Satellite

#### Data Schema: Managed Host (`satellite_hosts`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database or fixture ID. |
| `source_host_id` | string | **Yes** | Satellite host ID or UUID (max 100 chars). |
| `name` | string | **Yes** | FQDN of the managed host (max 255 chars). |
| `ip_address` | string \| `null` | No | Managed host IP address. |
| `operating_system` | string \| `null` | No | OS distribution & release version. |
| `organization_id` | integer \| `null` | No | Satellite organization ID. |
| `location_id` | integer \| `null` | No | Satellite location ID. |
| `source_payload` | object \| `null` | No | Content view and capsule metadata. |

#### Host Creation Payload (`POST /api/v1/satellite/hosts`)
```json
{
  "source_host_id": "sat-host-001",
  "name": "srv-prod-app-01.indusind.local",
  "ip_address": "192.0.2.10",
  "operating_system": "Red Hat Enterprise Linux 9.4",
  "organization_id": 1,
  "location_id": 1
}
```

#### Job Execution Launch Payload (`POST /api/v1/satellite/jobs`)
```json
{
  "template_id": "job-template-001",
  "host_ids": [
    "sat-host-001",
    "sat-host-002"
  ],
  "inputs": {
    "package_name": "openssl",
    "check_mode": false
  }
}
```

---

### 2.5 Squad1 Vulnerability Management & Exception Handling

Squad1 provides vulnerability discovery and exception tracking under BRD Section 4.2 (Table 12 and Table 59). In accordance with BRD business rules:
- Vulnerabilities are correlated to assets via `Target` and unique identifier `VulnerabilityNo`.
- Active exceptions are governed via `Exception_ID` and `Exception_END_Date`. If an exception has not expired, the vulnerability is suppressed from automated patching workflows.

#### Data Schema: Squad1 Vulnerability (`squad1_vulnerabilities`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database or fixture ID. |
| `vulnerability_no` | string | **Yes** | Unique Squad1 vulnerability number (max 100 chars). Idempotency key. |
| `target` | string | **Yes** | Target server IP or hostname (max 255 chars). |
| `vulnerability_name`| string | **Yes** | Vulnerability name or description (1–500 chars). |
| `severity` | string \| `null` | No | Severity level (`Critical`, `High`, `Medium`, `Low`, `Informational`). |
| `cve_id` | string \| `null` | No | Associated CVE identifier (e.g. `CVE-2024-21626`). |
| `status` | string \| `null` | No | Finding status (`Open`, `In Review`, `Exception Approved`, `Resolved`). |
| `exception_id` | string \| `null` | No | Formal Squad1 business exception ticket number. |
| `exception_end_date`| date string \| `null`| No | Date (`YYYY-MM-DD`) until which the exception is active. |
| `source_payload` | object \| `null` | No | Raw Squad1 scan and assessment details. |

#### Vulnerability POST Payload (`POST /api/v1/squad1/vulnerabilities`)
```json
{
  "vulnerability_no": "SQ1-VULN-2026-001",
  "target": "192.0.2.10",
  "vulnerability_name": "OpenSSH Terrapin Attack Vulnerability",
  "severity": "High",
  "cve_id": "CVE-2023-48795",
  "status": "Exception Approved",
  "exception_id": "EXC-SEC-2026-881",
  "exception_end_date": "2026-12-31"
}
```
The BRD field `severity` is accepted on create and returned alongside the normalized database field `risk_rating`.

#### Exception List Output (`GET /api/v1/squad1/exceptions`)
```json
{
  "items": [
    {
      "id": 1,
      "vulnerability_no": "SQ1-VULN-2026-001",
      "target": "192.0.2.10",
      "vulnerability_name": "OpenSSH Terrapin Attack Vulnerability",
      "cve_id": "CVE-2023-48795",
      "exception_id": "EXC-SEC-2026-881",
      "exception_end_date": "2026-12-31",
      "status": "Exception Approved",
      "is_expired": false
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```

---

### 2.6 Microsoft SCCM 2509 Enterprise Patch Management

SCCM 2509 models Windows patching as specified in BRD Section 4.6 (Table 20) and Section 8.5.5. The current `POST /api/v1/sccm/jobs` records a simulated deployment; the API provider has read-only inventory calls, so it does not yet submit a live SCCM deployment.
- **Client Readiness Gate**: Prior to deployment, devices must have `client_active_status: true`. Inactive clients are rejected from automated remediation.
- **Target Exceptions**: Targets matching an active Squad1 exception are marked `Skipped`; unknown SCCM devices remain `Unknown` and are not marked successful.
- **Compliance Tracking**: Deployment execution aggregates compliance statuses across all target assets into `Compliant`, `In Progress`, `Error`, `Unknown`, and `Skipped`.

#### Data Schema: SCCM Device (`sccm_devices`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database or fixture ID. |
| `source_device_id` | string | **Yes** | SCCM Resource ID or GUID (max 100 chars). |
| `hostname` | string | **Yes** | Device NetBIOS or DNS hostname (max 255 chars). |
| `ip_address` | string \| `null` | No | Device IP address. |
| `operating_system` | string \| `null` | No | Windows edition (e.g. `Windows Server 2022 Datacenter`). |
| `client_version` | string \| `null` | No | SCCM agent version (e.g. `5.00.9128.1000`). |
| `client_active_status`| boolean | No | `true` if client is active and communicating with Site Server. |
| `last_active_time` | date-time string | No | Timestamp of latest agent heartbeat. |
| `source_payload` | object \| `null` | No | SCCM WMI/SMS provider inventory properties. |

#### Deployment Launch Payload (`POST /api/v1/sccm/jobs`)
```json
{
  "deployment_id": "sccm-dep-001",
  "targets": [
    {
      "server_ci_id": "CI-SERVER-WIN-01",
      "resource_id": "RES-WIN-1001",
      "hostname": "win-app01.indusind.local"
    }
  ],
  "maintenance_window": {
    "start": "2026-11-02T22:00:00Z",
    "end": "2026-11-03T02:00:00Z"
  },
  "reboot_policy": "SuppressIfUserLoggedOn"
}
```

#### Deployment Execution Status (`GET /api/v1/sccm/jobs/{job_id}`)
```json
{
  "id": 1,
  "source_job_id": "RUN-WIN-001",
  "deployment_id": "sccm-dep-001",
  "status": "completed",
  "total_targets": 1,
  "compliant_count": 1,
  "in_progress_count": 0,
  "error_count": 0,
  "skipped_count": 0,
  "created_at": "2026-10-27T10:00:00Z",
  "asset_details": [
    {
      "id": 1,
      "resource_id": "RES-WIN-1001",
      "hostname": "win-app01.indusind.local",
      "status": "Compliant",
      "reboot_pending": false
    }
  ]
}
```

### 2.7 Ansible Automation Platform / AWX

The AAP API uses a configured bearer token and API root (`/api/controller/v2` by default; override with `ANSIBLE_API_PREFIX` for older AWX deployments). The token is read from `ANSIBLE_API_KEY` and is not stored in the database.

#### Patch Job Launch Request (`POST /api/v1/ansible/jobs`)

```json
{
  "job_template_id": "6",
  "limit": "rhel-host-01.example.com",
  "extra_vars": {"package_state": "latest"}
}
```

`limit` must contain exact hostnames or IPs; broad patterns are rejected. Targets with active Squad1 exceptions are blocked. The template must already have the required inventory and machine credentials configured in AAP. Job execution details are persisted in `ansible_job_runs` with the remote job ID, template ID, status, target limit, extra variables, timestamps, and source response payload.

| Launch request field | Type | Required | Meaning |
|---|---|:---:|---|
| `job_template_id` | string | Yes | AAP controller job template ID. |
| `limit` | string | Yes | Explicit Ansible host pattern to constrain targets. |
| `extra_vars` | object | No | Variables accepted by the selected template. |

The job detail response includes the local `id`, remote `job_id`, `job_template_id`, `status`, `limit`, `extra_vars`, `started_at`, `finished_at`, and `source_payload`. Connection responses contain `connected`, `controller`, and `api_version` without returning the configured token.

The read-only connection check is `GET /api/v1/ansible/connection`; template listing is `GET /api/v1/ansible/job-templates`; job status and cancellation use `/api/v1/ansible/jobs/{id}` and `/api/v1/ansible/jobs/{id}/cancel`.

---

## Canonical BRD Route Catalog

The table below lists the main public operations. The generated OpenAPI document at `/openapi.json` is the authoritative complete route list. VPM360 routes are distinct from the vendor routes its providers call; see the [BRD endpoint coverage and readiness notes](docs/BRD_INTEGRATION_ENDPOINT_COVERAGE.md) for both layers and client dependencies.

| Integration | Method | Endpoint Path | Function / BRD Reference |
|---|---|---|---|
| **Tenable** | `GET` | `/api/v1/tenable/findings` | List vulnerability findings (supports `limit=50000`) |
| | `POST` | `/api/v1/tenable/findings` | Create or update a vulnerability finding |
| | `GET` | `/api/v1/tenable/findings/{id}` | Retrieve finding by database ID |
| | `GET` | `/api/v1/tenable/scans` | List scanner execution metadata |
| | `POST` | `/api/v1/tenable/import` | Synchronize findings into PostgreSQL in 500-chunk batches |
| **CMDB** | `GET` | `/api/v1/cmdb/servers` | List server CIs (supports `limit=50000`) |
| | `POST` | `/api/v1/cmdb/servers` | Create a new server CI record |
| | `GET` | `/api/v1/cmdb/servers/{id}` | Retrieve server CI by ID |
| | `PATCH` | `/api/v1/cmdb/servers/{id}` | Update server CI attributes (BRD 4.8 Patch Writeback) |
| | `GET` | `/api/v1/cmdb/correlate` | Correlate IP address via query parameter (`?ip_address=`) |
| | `GET` | `/api/v1/cmdb/correlate/{ip}` | Correlate IP address to server CI (BRD Section 4.3) |
| | `GET` | `/api/v1/cmdb/middleware` | List middleware CIs |
| | `GET` | `/api/v1/cmdb/databases` | List database CIs |
| | `GET` | `/api/v1/cmdb/relationships` | List CI-to-CI dependency relationships |
| | `POST` | `/api/v1/cmdb/import` | Synchronize servers, middleware, and databases |
| **ITSM** | `GET` | `/api/v1/itsm/changes` | List change requests (supports `limit=50000`) |
| | `POST` | `/api/v1/itsm/changes` | Create change request with 19 BRD QA fields |
| | `GET` | `/api/v1/itsm/changes/{id}` | Retrieve change request by ID |
| | `PATCH` | `/api/v1/itsm/changes/{id}` | Update change request attributes or status |
| | `GET` | `/api/v1/itsm/changes/{id}/worklogs` | List worklogs for a change request |
| | `POST` | `/api/v1/itsm/changes/{id}/worklogs` | Add worklog entry to a change request |
| | `POST` | `/api/v1/itsm/import` | Synchronize change requests and worklogs |
| **Satellite**| `GET` | `/api/v1/satellite/hosts` | List Satellite managed hosts (supports `limit=50000`, BRD S1) |
| | `POST` | `/api/v1/satellite/hosts` | Create or update managed host |
| | `GET` | `/api/v1/satellite/job-templates` | List approved Ansible job templates (BRD S2) |
| | `POST` | `/api/v1/satellite/jobs` | Record a simulated job request; the public route does not launch a remote patch job (BRD S3) |
| | `GET` | `/api/v1/satellite/jobs/{id}` | Read the VPM360 stored job record (BRD S4) |
| | `GET` | `/api/v1/satellite/jobs/{id}/hosts/{h_id}` | Read a stored per-host job result (BRD S5) |
| | `GET` | `/api/v1/satellite/jobs/{id}/hosts/{h_id}/raw` | Read stored raw output or request the provider's S6 raw output in API mode |
| | `POST` | `/api/v1/satellite/jobs/{id}/cancel` | Cancel a pending VPM360 simulated job (BRD S7); remote cancellation is not wired to this route |
| | `POST` | `/api/v1/satellite/import` | Synchronize hosts and job templates |
| **Squad1** | `GET` | `/api/v1/squad1/vulnerabilities` | List vulnerabilities (supports `limit=50000`, BRD 4.2) |
| | `POST` | `/api/v1/squad1/vulnerabilities` | Ingest or update a vulnerability finding |
| | `GET` | `/api/v1/squad1/exceptions` | List active vulnerability exceptions (`Exception_ID`) |
| | `POST` | `/api/v1/squad1/import` | Synchronize Squad1 findings and exceptions |
| **SCCM** | `GET` | `/api/v1/sccm/devices` | List managed Windows devices (supports `limit=50000`, BRD 4.6) |
| | `GET` | `/api/v1/sccm/collections` | List SCCM device collections |
| | `GET` | `/api/v1/sccm/deployments` | List SCCM software update deployments |
| | `POST` | `/api/v1/sccm/jobs` | Record a simulated guarded deployment run; no remote SCCM deployment is submitted |
| | `GET` | `/api/v1/sccm/jobs/{id}` | Retrieve deployment run breakdown |
| | `POST` | `/api/v1/sccm/import` | Synchronize SCCM inventory and deployment states |
| **Ansible AAP** | `GET` | `/api/v1/ansible/connection` | Check configured controller authentication without launching a job |
| | `GET` | `/api/v1/ansible/job-templates` | List controller job templates |
| | `POST` | `/api/v1/ansible/jobs` | Launch an Ansible job with an explicit target `limit` and `extra_vars` |
| | `GET` | `/api/v1/ansible/jobs/{id}` | Refresh and persist controller job status |
| | `POST` | `/api/v1/ansible/jobs/{id}/cancel` | Request controller job cancellation |

---


## 20k+ Dataset Throughput & Idempotency

1. **50,000 Pagination Upper Bound**: All listing endpoints permit `limit <= 50000`, allowing consumers to fetch massive datasets in single round-trips without encountering `422 Unprocessable Entity` errors.
2. **In-Memory Fixture Cache**: Global `_FIXTURE_CACHE` stores parsed JSON payloads keyed by file modification time (`st_mtime`). Repeated reads of 20,000 records return in under **1 millisecond**.
3. **Fast-Path Normalization**: Avoids deep re-normalization when reading fixture rows that already contain normalized attributes, cutting processing time from ~50 seconds to **0.009 seconds**.
4. **500-Item Chunked Batch Ingestion**: Replaces slow per-row SQL flushes and savepoints with vectorized `filter(source_id.in_(chunk_ids))` lookups and atomic chunk commits, preventing PostgreSQL connection stalls.
5. **Idempotency Guarantees**: Repeated POST requests update records in place and return the current state, preventing duplicate key errors across the configured integrations.

---

## Fixture Directory Structure

Simulation fixture files are stored under `fixtures/`:

```text
fixtures/
├── cmdb/
│   ├── databases.json          # Database CIs
│   ├── middleware.json         # Middleware CIs
│   ├── multidatabases.json     # Large dataset
│   ├── multimiddleware.json    # Large dataset
│   ├── multiservers.json       # Large 20k servers dataset
│   ├── relationships.json      # Inter-CI relationships
│   └── servers.json            # Server CIs
├── itsm/
│   ├── change_history.json     # Change audit records
│   ├── changes.json            # Change requests
│   ├── multichanges.json       # Change requests dataset
│   ├── multiworklogs.json      # Large worklogs dataset
│   └── worklogs.json           # Activity logs
├── satellite/
│   ├── hosts.json              # Managed hosts
│   ├── job_host_results.json   # Per-host execution logs
│   ├── job_runs.json           # Execution job runs
│   └── job_templates.json      # Job templates
├── sccm/
│   ├── collections.json        # Baseline device collections (3 sample records)
│   ├── deployment_runs.json    # Baseline deployment runs (2 sample records)
│   ├── deployments.json        # Baseline patch deployments (2 sample records)
│   └── devices.json            # Baseline Windows devices (3 sample records)
├── squad1/
│   └── vulnerabilities.json    # Baseline vulnerabilities with exceptions (3 sample records)
└── tenable/
    ├── findings.json           # Baseline vulnerability findings
    ├── multifindings.json      # Large 20k dataset for stress testing
    ├── multiscans.json         # Large 20k scans dataset
    └── scans.json              # Scanner jobs
```

> **Note on Data Volume**: Per user requirements, Squad1 and SCCM 2509 fixtures are initialized with lightweight, synthetic baseline records (~3 records each) rather than 20,000 records. Full 20,000-record datasets can be imported into their respective directories when ready.

---

## Getting Started & Quickstart

### Environment Configuration

Create or update `.env` in the project root:

```ini
APP_NAME=VPM360 Simulator
ENVIRONMENT=development
DATABASE_URL=postgresql+psycopg://appuser:ChangeMe13_Strong@localhost:5433/appdb

# Provider Modes: 'json' (simulation) or 'api' (live vendor)
TENABLE_PROVIDER=json
CMDB_PROVIDER=json
ITSM_PROVIDER=json
SATELLITE_PROVIDER=json
SQUAD1_PROVIDER=json
SCCM_PROVIDER=json

# Pagination ceiling
TENABLE_MAX_SCAN_RESULTS=50000
```

### Database Setup & Migrations

Ensure PostgreSQL is accessible, then apply the Alembic migration to create the registered VPM360 integration tables:

```bash
# Run database schema migrations
alembic upgrade head
```

### Running the Application

Start the FastAPI application with Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API documentation will be available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Building the FastAPI Docker Image

The root `Dockerfile` builds the FastAPI/Uvicorn service. `compose.yaml` starts it with a separate PostgreSQL 16 container, waits for PostgreSQL, and applies Alembic migrations before starting the API. Set `POSTGRES_PASSWORD` before starting (keep it in your deployment secret store in AWS):

```powershell
$env:POSTGRES_PASSWORD = "Use-A-Strong-Alphanumeric-Secret"
docker compose -f compose.yaml up --build -d
```

The API is published on port `8000`; PostgreSQL is published on host port `5433` (container port `5432`). The API connects to PostgreSQL over the private Compose network. Set `API_HOST_PORT` or `POSTGRES_HOST_PORT` to change the host-side ports. For AWS EC2 or another Docker host, allow inbound traffic to the API port only; keep PostgreSQL private and do not expose its host port publicly. Use an AWS-managed database for production data durability. Compose is for Docker hosts; ROSA deployments use OpenShift resources instead of Docker Compose.

The API readiness check is `/api/v1/ready`; Swagger is `/docs`. The Compose database uses a named volume so its data survives container restarts. Do not include `.env` in the image or commit production credentials.

After the image is deployed to an always-on container host, set the Streamlit Cloud `API_BASE_URL` secret to that service's public URL ending in `/api/v1`. The Streamlit Cloud app URL itself is not the FastAPI endpoint.

### Running the Streamlit Frontend

Start the FastAPI/Uvicorn backend first, then run Streamlit in a second terminal:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000/api/v1"
streamlit run streamlit_app.py
```

The frontend reads the backend's OpenAPI schema and exposes every documented operation in the **All API Routes** tab, along with integration dashboards for Tenable, Squad1, CMDB, ITSM, Satellite and SCCM. The dashboard uses a fixed 100-record preview and has no record-count slider.

For Streamlit Cloud, deploy the FastAPI/Uvicorn backend separately at a URL reachable from the Streamlit app, then add this to the Streamlit app's Secrets:

```toml
API_BASE_URL = "https://your-fastapi-service.example.com/api/v1"
```

Do not use `localhost` or `127.0.0.1` in the Cloud secret: those addresses refer to the Streamlit container, not your computer or the separate FastAPI host. The frontend calls FastAPI server-to-server, so the backend needs to be network reachable from Streamlit Cloud.

### Running the Test Suite

Execute the integration test suite validating canonical routes, 20k query throughput, idempotency, Squad1, and SCCM:

```bash
pytest tests/test_all_integrations.py -v -o pythonpath=.
```

All 10 integration suites run and pass 100%:
```text
tests/test_all_integrations.py::test_tenable_canonical_routes PASSED
tests/test_all_integrations.py::test_cmdb_canonical_routes_and_correlation PASSED
tests/test_all_integrations.py::test_itsm_canonical_routes PASSED
tests/test_all_integrations.py::test_satellite_canonical_routes PASSED
tests/test_all_integrations.py::test_system_and_health_routes PASSED
tests/test_all_integrations.py::test_large_dataset_queries_up_to_20k PASSED
tests/test_all_integrations.py::test_idempotency_and_duplicate_handling PASSED
tests/test_all_integrations.py::test_squad1_canonical_routes PASSED
tests/test_all_integrations.py::test_sccm_canonical_routes PASSED
tests/test_all_integrations.py::test_extended_endpoints PASSED
```
