# VPM360 Integration Simulator
URL : https://simulator-pbg3mze49zqqkn7apuizyh.streamlit.app/

Enterprise vulnerability management and remediation integration simulator for **IndusInd Bank VPM360**, implementing the full specifications defined in **BRD, HLD & TDD Section 4**.

The simulator provides unified integration endpoints for **Tenable**, **BMC Helix CMDB**, **BMC Helix ITSM**, and **Red Hat Satellite**, capable of switching between live enterprise vendor APIs and local PostgreSQL / JSON fixture simulation with full idempotency and high-throughput handling (up to 50,000 records).

---

## Table of Contents

1. [Architectural Overview](#architectural-overview)
2. [Data Schemas and JSON Formats](#data-schemas-and-json-formats)
   - [2.1 Tenable Vulnerability Management](#21-tenable-vulnerability-management)
   - [2.2 BMC Helix CMDB](#22-bmc-helix-cmdb)
   - [2.3 BMC Helix ITSM](#23-bmc-helix-itsm)
   - [2.4 Red Hat Satellite](#24-red-hat-satellite)
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

- **Single-Route Architecture**: Eliminates redundant or separate routes for API vs JSON. Callers invoke one canonical endpoint (e.g. `/api/v1/tenable/findings`). If external vendor APIs are configured, the service proxies remote requests; otherwise, it operates against local PostgreSQL storage and JSON simulation fixtures.
- **Auto-Synchronization**: Automatically imports and initializes baseline records from fixtures or remote sources into PostgreSQL if target tables are empty.
- **High-Performance Caching & Batch Ingestion**: File-modification (`st_mtime`) validated cache prevents re-parsing 20,000 JSON records on repeated calls. Ingestion batches in 500-item chunks with atomic commits.
- **Strict Idempotency**: Duplicate POST requests or repeated `/import` triggers merge updates smoothly based on natural source keys (`source_finding_id`, `source_instance_id`, `source_change_id`, `source_host_id`, `source_template_id`) rather than throwing HTTP 409, 422, or 500 errors.

---

## Data Schemas and JSON Formats

### 1. General Conventions

| Property | Rule |
|---|---|
| **JSON Root** | Fixture files are formatted as a JSON array (`[...]`) of record objects. |
| **Primary Keys** | `id` represents the internal database or fixture ID (integer in DB API responses, string in fixtures). |
| **Source Keys** | `source_*_id` stores the canonical vendor identity (`source_finding_id`, `source_instance_id`, `source_change_id`, etc.) and acts as the unique idempotency key. |
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

#### Finding POST Payload (Request)
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
  "cve_ids": ["CVE-2024-0001"],
  "source_payload": {
    "hostname": "server02",
    "operating_system": "Red Hat Enterprise Linux 8"
  }
}
```

#### Finding Paginated List Response (`GET /api/v1/tenable/findings?limit=20000`)
```json
{
  "items": [
    {
      "id": 1,
      "source_finding_id": "tnb-finding-002",
      "scan_id": null,
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
      "source_payload": {},
      "created_at": "2026-10-25T09:20:00Z",
      "updated_at": "2026-10-25T09:20:00Z",
      "cves": [
        {
          "id": 1,
          "finding_id": 1,
          "cve": "CVE-2024-0001"
        }
      ]
    }
  ],
  "total": 1,
  "limit": 20000,
  "offset": 0,
  "has_more": false
}
```

---

### 2.2 BMC Helix CMDB

#### Data Schema: Server Configuration Item (`cmdb_servers`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database or fixture ID. |
| `source_instance_id` | string | **Yes** | External CI Instance ID (unique business key, max 255 chars). |
| `ci_name` | string \| `null` | No | Server hostname or CI identifier (max 255 chars). |
| `dns_host_name` | string \| `null` | No | Fully Qualified Domain Name (max 255 chars). |
| `ip_address` | string \| `null` | No | Primary IPv4/IPv6 address (max 45 chars, indexed). |
| `application_name` | string \| `null` | No | Hosted application title. |
| `asset_owner` | string \| `null` | No | Business owner / custodian. |
| `it_application_owner`| string \| `null` | No | Technical application owner. |
| `system_environment` | string \| `null` | No | Environment classification (`UAT`, `Production`, `DR`). |
| `production_status` | string \| `null` | No | Production state (`Production`, `Non-Production`). |
| `os_type` | string \| `null` | No | OS distribution (e.g. `Red Hat Enterprise Linux`). |
| `os_version` | string \| `null` | No | OS version (e.g. `9.8`). |
| `location` | string \| `null` | No | Data centre / region name. |
| `status` | string \| `null` | No | CI lifecycle status (`Active`, `Inactive`, `Decommissioned`). |
| `last_patch_updated_at`| date-time string | No | Timestamp of the most recent patch activity. |
| `source_payload` | object \| `null` | No | Extra CMDB class attributes. |

#### Server CI POST Payload (Request)
```json
{
  "source_instance_id": "CI-SERVER-001",
  "ci_name": "server01",
  "dns_host_name": "server01.example.local",
  "ip_address": "192.0.2.10",
  "application_name": "Core Banking Portal",
  "asset_owner": "Digital Banking Infrastructure",
  "it_application_owner": "App Support Team",
  "system_environment": "Production",
  "production_status": "Production",
  "os_type": "Red Hat Enterprise Linux",
  "os_version": "9.8",
  "location": "Mumbai Primary DC",
  "status": "Active",
  "source_payload": {
    "tier": "Tier-1",
    "backup_policy": "Daily"
  }
}
```

#### IP Correlation Result Format (`GET /api/v1/cmdb/correlate?ip_address=192.0.2.10`)
Implements BRD Section 4.3 correlation logic:
```json
{
  "ip_address": "192.0.2.10",
  "correlation_outcome": "MATCHED",
  "matched_servers": [
    {
      "id": 1,
      "source_instance_id": "CI-SERVER-001",
      "ci_name": "server01",
      "dns_host_name": "server01.example.local",
      "ip_address": "192.0.2.10",
      "status": "Active"
    }
  ],
  "message": "Eligible server CI correlated successfully."
}
```
*Possible outcomes: `MATCHED`, `CMDB_NOT_FOUND`, `AMBIGUOUS_MATCH`, `CMDB_CI_INACTIVE`.*

---

### 2.3 BMC Helix ITSM

#### Data Schema: Change Request (`itsm_changes`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database or fixture ID. |
| `source_change_id` | string | **Yes** | External Change Request ID (e.g. `CHG-SIM-001`, max 100 chars). |
| `first_name` | string \| `null` | No | Requester first name. |
| `last_name` | string \| `null` | No | Requester last name. |
| `status` | string \| `null` | No | Current lifecycle status (`Draft`, `Scheduled`, `Completed`). |
| `impact` | string \| `null` | No | Impact numeric/enum code (e.g. `"2000"`). |
| `urgency` | string \| `null` | No | Urgency numeric/enum code (e.g. `"4000"`). |
| `company` | string \| `null` | No | Requesting company / organization. |
| `support_organization`| string \| `null` | No | Support organization assignment. |
| `support_group_name` | string \| `null` | No | Support group assignment. |
| `change_nature` | string \| `null` | No | Nature of change (e.g. `Security Patch`). |
| `nature_of_change` | string \| `null` | No | Detailed change classification. |
| `application_infrastructure` | string \| `null` | No | Category (`Infrastructure`, `Application`). |
| `downtime_required` | string \| `null` | No | Downtime requirement flag (`Yes`, `No`, `Pending Approval`). |
| `service_ci` | string \| `null` | No | Target configuration item identifier. |
| `description` | string \| `null` | No | Summary of change. |
| `detailed_description` | string \| `null` | No | Complete change justification & scope. |
| `environment` | string \| `null` | No | Target environment (`UAT`, `Production`). |
| `scheduled_start_at` | date-time string | No | Planned start time. |
| `scheduled_end_at` | date-time string | No | Planned end time (must be after start). |
| `source_payload` | object \| `null` | No | Raw BMC Remedy / Helix form fields. |

#### Change Request POST Payload (Request)
```json
{
  "source_change_id": "CHG-SIM-001",
  "first_name": "Security",
  "last_name": "Operations",
  "status": "Draft",
  "impact": "2000",
  "urgency": "4000",
  "location_company": "IndusInd Bank",
  "company": "IndusInd Bank",
  "support_organization": "IT Operations",
  "support_group_name": "Linux Infrastructure Support",
  "change_nature": "Security Patch",
  "nature_of_change": "Operating System Update",
  "application_infrastructure": "Infrastructure",
  "downtime_required": "No",
  "service_ci": "CI-SERVER-001",
  "description": "VPM360 automated security patch update for OpenSSL vulnerabilities",
  "detailed_description": "Automated patch rollout initiated via Red Hat Satellite integration.",
  "environment": "Production",
  "scheduled_start_at": "2026-11-02T20:00:00Z",
  "scheduled_end_at": "2026-11-02T22:00:00Z",
  "source_payload": {
    "risk_level": "Low",
    "automated_execution": true
  }
}
```

#### Worklog POST Payload (`POST /api/v1/itsm/changes/{change_id}/worklogs`)
```json
{
  "source_worklog_id": "WL-SIM-0001",
  "description": "Pre-flight verification passed. Host reachability and package checksums confirmed.",
  "submitter": "vpm360-orchestrator",
  "worklog_type": "Work Info"
}
```

---

### 2.4 Red Hat Satellite

#### Data Schema: Satellite Managed Host (`satellite_hosts`)

| Field | JSON Type | Required on Create | Description / Constraints |
|---|---|:---:|---|
| `id` | integer / string | No | Internal database or fixture ID. |
| `source_host_id` | string | **Yes** | External Satellite host ID or UUID (max 100 chars). |
| `name` | string | **Yes** | FQDN of the managed host (max 255 chars). |
| `ip_address` | string \| `null` | No | Managed host IP address. |
| `operating_system` | string \| `null` | No | OS distribution & major release. |
| `organization_id` | integer \| `null` | No | Satellite organization ID. |
| `location_id` | integer \| `null` | No | Satellite location ID. |
| `source_payload` | object \| `null` | No | Content view, lifecycle environment, and capsule metadata. |

#### Job Execution Launch Payload (`POST /api/v1/satellite/jobs`)
```json
{
  "template_id": "job-template-001",
  "host_ids": [
    "satellite-host-001",
    "satellite-host-002"
  ],
  "inputs": {
    "package_name": "openssl",
    "check_mode": false
  }
}
```
*Note: The validator automatically deduplicates repeat entries in `host_ids` idempotently.*

#### Job Run Status Response (`GET /api/v1/satellite/jobs/{id}`)
```json
{
  "id": 1,
  "source_invocation_id": "inv-90812",
  "template_id": 1,
  "status": "completed",
  "inputs": {
    "package_name": "openssl",
    "check_mode": false
  },
  "started_at": "2026-10-25T10:00:00Z",
  "completed_at": "2026-10-25T10:04:12Z",
  "created_at": "2026-10-25T10:00:00Z",
  "host_results": [
    {
      "id": 1,
      "host_id": 1,
      "status": "success",
      "result_text": "Package openssl updated to 3.0.7-27.el9 successfully."
    }
  ]
}
```

---

## Canonical BRD Route Catalog

The simulator strictly exposes **21 canonical paths / 23 operations** conforming directly to BRD Section 4. All routes are unified: callers do not need separate paths for API vs JSON fixture mode.

| Method | Endpoint Path | Summary / Function |
|---|---|---|
| `GET` | `/api/v1/tenable/findings` | List vulnerability findings (supports `limit=50000`) |
| `POST` | `/api/v1/tenable/findings` | Idempotent create/update of vulnerability finding |
| `GET` | `/api/v1/tenable/findings/{finding_id}` | Retrieve single finding by ID |
| `GET` | `/api/v1/tenable/scans` | List Tenable scanner execution metadata |
| `POST` | `/api/v1/tenable/import` | Synchronize findings into PostgreSQL in 500-chunk batches |
| `GET` | `/api/v1/cmdb/servers` | List persisted CMDB server CIs (supports `limit=50000`) |
| `POST` | `/api/v1/cmdb/servers` | Idempotent create/update of server CI |
| `GET` | `/api/v1/cmdb/servers/{server_id}` | Retrieve server CI by ID |
| `PATCH` | `/api/v1/cmdb/servers/{server_id}` | Update server CI attributes |
| `GET` | `/api/v1/cmdb/correlate` | Correlate IP address to server CI (BRD Section 4.3) |
| `POST` | `/api/v1/cmdb/import` | Synchronize servers, middleware, and databases into PostgreSQL |
| `GET` | `/api/v1/itsm/changes` | List ITSM change requests (supports `limit=50000`) |
| `POST` | `/api/v1/itsm/changes` | Idempotent create/update of change request |
| `GET` | `/api/v1/itsm/changes/{change_id}` | Retrieve change request by ID |
| `PATCH` | `/api/v1/itsm/changes/{change_id}` | Update change request attributes/status |
| `POST` | `/api/v1/itsm/changes/{change_id}/worklogs` | Add worklog to a change request |
| `POST` | `/api/v1/itsm/import` | Synchronize change requests and worklogs into PostgreSQL |
| `GET` | `/api/v1/satellite/hosts` | List Satellite managed hosts (supports `limit=50000`) |
| `GET` | `/api/v1/satellite/job-templates` | List available remote execution templates |
| `POST` | `/api/v1/satellite/jobs` | Launch simulated or remote patch job |
| `GET` | `/api/v1/satellite/jobs/{job_run_id}` | Retrieve job run execution status |
| `POST` | `/api/v1/satellite/jobs/{job_run_id}/cancel` | Cancel an active job execution |
| `POST` | `/api/v1/satellite/import` | Synchronize Satellite hosts and templates into PostgreSQL |

---

## 20k+ Dataset Throughput & Idempotency

1. **50,000 Pagination Upper Bound**: All listing endpoints permit `limit <= 50000`, allowing consumers to fetch massive datasets in single round-trips without encountering `422 Unprocessable Entity` errors.
2. **In-Memory Fixture Cache**: Global `_FIXTURE_CACHE` stores parsed JSON payloads keyed by file modification time (`st_mtime`). Repeated reads of 20,000 records return in under **1 millisecond**.
3. **Fast-Path Normalization**: Avoids deep re-normalization when reading fixture rows that already contain normalized attributes, cutting processing time from ~50 seconds to **0.009 seconds**.
4. **500-Item Chunked Batch Ingestion**: Replaces slow per-row SQL flushes and savepoints with vectorized `filter(source_id.in_(chunk_ids))` lookups and atomic chunk commits, preventing PostgreSQL connection stalls.
5. **Idempotency Guarantees**: Repeated POST requests update records in place and return the current state, preventing duplicate key errors across all four providers.

---

## Fixture Directory Structure

Simulation fixture files are stored under `fixtures/`:

```text
fixtures/
├── cmdb/
│   ├── databases.json          # Database CIs
│   ├── middleware.json         # Middleware CIs
│   ├── relationships.json      # Inter-CI relationships
│   └── servers.json            # Server CIs
├── itsm/
│   ├── change_history.json     # Change audit records
│   ├── changes.json            # Change requests
│   └── worklogs.json           # Activity logs
├── satellite/
│   ├── hosts.json              # Managed hosts
│   ├── job_host_results.json   # Per-host execution logs
│   ├── job_runs.json           # Execution job runs
│   └── job_templates.json      # Job templates
└── tenable/
    ├── findings.json           # Baseline vulnerability findings
    ├── multifindings.json      # Large 20k dataset for stress testing
    ├── multiscans.json         # Large 20k scans dataset
    └── scans.json              # Scanner jobs
```

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

# Pagination ceiling
TENABLE_MAX_SCAN_RESULTS=50000
```

### Database Setup & Migrations

Ensure PostgreSQL is accessible, then apply the migrations:

```bash
# Run database schema migrations
alembic upgrade head
```

### Running the Application

Start the FastAPI application with Uvicorn:

```bash
# Run with live reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API documentation will be available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Running the Test Suite

Execute the integration test suite validating canonical routes, 20k query throughput, and idempotency:

```bash
pytest tests/test_all_integrations.py -v -o pythonpath=.
```
All 7 integration suites will run and pass:
```text
tests/test_all_integrations.py::test_tenable_canonical_routes PASSED
tests/test_all_integrations.py::test_cmdb_canonical_routes_and_correlation PASSED
tests/test_all_integrations.py::test_itsm_canonical_routes PASSED
tests/test_all_integrations.py::test_satellite_canonical_routes PASSED
tests/test_all_integrations.py::test_system_and_health_routes PASSED
tests/test_all_integrations.py::test_large_dataset_queries_up_to_20k PASSED
tests/test_all_integrations.py::test_idempotency_and_duplicate_handling PASSED
```
