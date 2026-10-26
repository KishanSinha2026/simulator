# VPM360 Simulator — Data Schemas and JSON Formats

This document describes the normalized data fields and JSON formats used by the Tenable, BMC Helix CMDB, BMC Helix ITSM, and Red Hat Satellite integrations. It covers the fields exposed by the Pydantic schemas and the example JSON fixtures used by the simulator.

> **Data-source note:** The examples below are synthetic demonstration data, not records from a real environment. Confirm vendor-specific field mappings against your own Tenable, BMC Helix, and Satellite API responses before enabling API mode.

## 1. General JSON conventions

| Convention | Description |
|---|---|
| JSON root | Fixture files contain a JSON array (`[...]`) of record objects. |
| `id` | Identifier used by the simulator fixture or its database record. Depending on provider, it may be a string in fixture mode and an integer in database/API response mode. |
| `source_*_id` | Identifier originating from an external integration. Keep it stable to support matching and deduplication. |
| `source_payload` | Optional JSON object for retaining additional source-system fields that do not have a dedicated normalized column. |
| Optional fields | Fields may be omitted from an input when optional. Responses and fixtures can explicitly use `null` for unavailable values. |
| Timestamps | Use ISO 8601 timestamps with an explicit timezone, preferably UTC, e.g. `2026-10-25T09:15:00Z`. |
| Numbers | JSON numbers must not be quoted. Identifiers represented as external IDs should remain strings even when they contain digits. |
| Booleans | Use JSON `true` or `false`, not strings. |
| Unknown fields | The documented Pydantic request schemas generally reject unknown fields (`extra="forbid"`). |

### Fixture locations

| Integration / record type | Expected fixture path |
|---|---|
| Tenable findings | `fixtures/tenable/findings.json` |
| CMDB servers | `fixtures/cmdb/servers.json` |
| CMDB middleware | `fixtures/cmdb/middleware.json` |
| CMDB databases | `fixtures/cmdb/databases.json` |
| ITSM changes | `fixtures/itsm/changes.json` |
| ITSM worklogs | `fixtures/itsm/worklogs.json` |
| Satellite hosts | `fixtures/satellite/hosts.json` |
| Satellite job templates | `fixtures/satellite/job_templates.json` |
| Satellite job runs | `fixtures/satellite/job_runs.json` |
| Satellite job host results | `fixtures/satellite/job_host_results.json` |

Use the canonical spelling `itsm` for new paths. If an existing checkout still has `fixtures/istm/`, move or recreate those files under `fixtures/itsm/` to match the provider configuration.

---

## 2. Tenable vulnerability data

### 2.1 Main finding fields

| Field | JSON type | Required on create? | Description / validation |
|---|---|---:|---|
| `id` | string or integer | No | Simulator/database identifier; usually generated or provided by a fixture. |
| `source_finding_id` | string or `null` | No | External finding identifier; maximum 150 characters. |
| `scan_id` | integer or `null` | No | Internal database scan reference when available. |
| `plugin_id` | integer | **Yes** | Must be greater than zero on finding creation. |
| `plugin_name` | string | **Yes** | Required, nonblank, maximum 500 characters. |
| `ip_address` | string or `null` | No | IPv4 or IPv6 text; maximum 45 characters. |
| `dns_name` | string or `null` | No | DNS/host name; maximum 255 characters. |
| `host_id` | string or `null` | No | Source host identifier. |
| `severity` | string or `null` | No | Vendor-normalized severity, e.g. `info`, `low`, `medium`, `high`, `critical`. |
| `synopsis` | string or `null` | No | Short finding summary. |
| `description` | string or `null` | No | Full finding description. |
| `plugin_output` | string or `null` | No | Output reported by the plugin. |
| `steps_to_remediate` | string or `null` | No | Remediation instructions. |
| `cvss_v3_base_score` | number or `null` | No | Score from 0 through 10. |
| `cvss_v4_base_score` | number or `null` | No | Score from 0 through 10. |
| `first_discovered` | date-time string or `null` | No | First discovery timestamp. |
| `last_observed` | date-time string or `null` | No | Most recent observation timestamp. |
| `repository` | string or `null` | No | Repository/network grouping; maximum 255 characters. |
| `protocol` | string or `null` | No | Protocol name, e.g. `tcp`. |
| `port` | integer or `null` | No | Valid range 0–65535 in the Pydantic schema. |
| `cve_ids` | array of strings | No | Create/input field; normalized to uppercase and deduplicated by the service. |
| `source_payload` | object or `null` | No | Additional raw source attributes. |

### 2.2 Tenable create/request JSON

`cve_ids` is accepted in the create payload. In the relational model, CVEs are represented as associated records rather than a single `cve_ids` column.

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
    "severity_id": 3,
    "hostname": "server02",
    "operating_system": "Red Hat Enterprise Linux 8",
    "status": "open"
  }
}
```

### 2.3 Tenable API response shape

A finding response adds the persisted `id`, `created_at`, `updated_at`, and `cves` properties. The paginated list response has this shape:

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
        {"id": 1, "finding_id": 1, "cve": "CVE-2024-0001"}
      ]
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```

### 2.4 Related relational entities

| Entity / table | Fields | Notes |
|---|---|---|
| `tenable_scans` | `id`, `source_scan_id`, `name`, `status`, `started_at`, `completed_at`, `source_payload`, `created_at`, `updated_at` | `source_scan_id` is a unique external scan identifier. |
| `tenable_findings` | Fields in the main finding table, plus `created_at`, `updated_at` | `scan_id` refers to the internal scan row ID when linked. |
| `tenable_finding_cves` | `id`, `finding_id`, `cve` | One row per CVE association; `(finding_id, cve)` is unique. |

---

## 3. BMC Helix CMDB data

### 3.1 Server CI schema (`cmdb_servers`)

| Field | JSON type | Required on create? | Description / validation |
|---|---|---:|---|
| `id` | string in fixture / integer in database response | No | Simulator/database identity. |
| `source_instance_id` | string | **Yes** | External CMDB instance ID; nonblank, maximum 255 characters. |
| `ci_name` | string or `null` | No | Configuration item name; maximum 255 characters. |
| `dns_host_name` | string or `null` | No | DNS host name; maximum 255 characters. |
| `ip_address` | string or `null` | No | IP address; maximum 45 characters. |
| `application_name` | string or `null` | No | Application associated with the CI. |
| `asset_owner` | string or `null` | No | Business/asset owner. |
| `it_application_owner` | string or `null` | No | IT application owner. |
| `system_environment` | string or `null` | No | Environment, e.g. `UAT`, `Production`. |
| `production_status` | string or `null` | No | Production classification. |
| `os_type` | string or `null` | No | Operating-system family. |
| `os_version` | string or `null` | No | Operating-system version. |
| `location` | string or `null` | No | Location or data centre. |
| `status` | string or `null` | No | CI lifecycle/status value. |
| `last_patch_updated_at` | date-time string or `null` | No | Last patch update timestamp. |
| `source_payload` | object or `null` | No | Extra attributes from BMC Helix or an intermediate source. |
| `created_at`, `updated_at` | date-time string | Response only | Database-managed timestamps. |

### 3.2 Server CI JSON

```json
{
  "id": "cmdb-server-001",
  "source_instance_id": "CI-SERVER-001",
  "ci_name": "server01",
  "dns_host_name": "server01.example.local",
  "ip_address": "192.0.2.10",
  "application_name": "Example Application",
  "asset_owner": "Example Infrastructure Team",
  "it_application_owner": "Example Application Team",
  "system_environment": "UAT",
  "production_status": "Non-Production",
  "os_type": "Red Hat Enterprise Linux",
  "os_version": "9.8",
  "location": "Example Data Centre",
  "status": "Active",
  "last_patch_updated_at": null,
  "source_payload": {
    "company": "Example Company",
    "asset_type": "Server",
    "support_group": "Example Infrastructure Support",
    "is_simulated": true
  }
}
```

### 3.3 Middleware CI (`cmdb_middleware`)

| Field | JSON type | Description |
|---|---|---|
| `id` | string in fixture / integer in database response | Internal fixture/database identity. |
| `source_instance_id` | string | Unique external CI identifier. |
| `ci_name` | string or `null` | Middleware CI name. |
| `server_instance_id` | string or `null` | External ID of the associated server CI. |
| `middleware_type` | string or `null` | Middleware product/type. |
| `version` | string or `null` | Installed version. |
| `status` | string or `null` | CI status. |
| `source_payload` | object or `null` | Additional source attributes. |
| `created_at`, `updated_at` | date-time strings | Database-managed fields in responses. |

```json
{
  "id": "ci-middleware-001",
  "source_instance_id": "CI-MIDDLEWARE-001",
  "ci_name": "middleware01",
  "server_instance_id": "CI-SERVER-001",
  "middleware_type": "Example Middleware",
  "version": "1.0",
  "status": "Active",
  "source_payload": {
    "product_name": "Example Middleware",
    "environment": "UAT",
    "is_simulated": true
  }
}
```

### 3.4 Database CI (`cmdb_databases`)

| Field | JSON type | Description |
|---|---|---|
| `id` | string in fixture / integer in database response | Internal fixture/database identity. |
| `source_instance_id` | string | Unique external CI identifier. |
| `ci_name` | string or `null` | Database CI name. |
| `server_instance_id` | string or `null` | External ID of the associated server CI. |
| `database_type` | string or `null` | Database engine/product. |
| `version` | string or `null` | Database version. |
| `status` | string or `null` | CI status. |
| `source_payload` | object or `null` | Additional source attributes. |
| `created_at`, `updated_at` | date-time strings | Database-managed fields in responses. |

```json
{
  "id": "ci-database-001",
  "source_instance_id": "CI-DATABASE-001",
  "ci_name": "database01",
  "server_instance_id": "CI-SERVER-001",
  "database_type": "PostgreSQL",
  "version": "16",
  "status": "Active",
  "source_payload": {
    "environment": "UAT",
    "is_simulated": true,
    "notes": "Synthetic database CI for local simulator testing."
  }
}
```

### 3.5 CMDB relationship (`cmdb_relationships`)

| Field | JSON type | Description |
|---|---|---|
| `id` | integer in database response | Internal relationship ID. |
| `source_relationship_id` | string | External relationship identifier. |
| `source_instance_id` | string | External ID of the source CI. |
| `destination_instance_id` | string | External ID of the destination CI. |
| `relationship_type` | string | Relationship label/type. |
| `source_payload` | object or `null` | Raw relationship data. |
| `created_at` | date-time string | Database-managed creation time. |

```json
{
  "source_relationship_id": "REL-SERVER-MIDDLEWARE-001",
  "source_instance_id": "CI-SERVER-001",
  "destination_instance_id": "CI-MIDDLEWARE-001",
  "relationship_type": "HOSTS",
  "source_payload": {"is_simulated": true}
}
```

---

## 4. BMC Helix ITSM data

### 4.1 Change request schema

| Field | JSON type | Required on create? | Description / validation |
|---|---|---:|---|
| `id` | string in fixture / integer in database response | No | Simulator/database identity. |
| `source_change_id` | string | **Yes** | External change ID; nonblank, maximum 100 characters. |
| `first_name`, `last_name` | string or `null` | No | Requester/submitter name fields. |
| `status` | string or `null` | No | Change status. |
| `impact`, `urgency` | string or `null` | No | Preserve source values as strings where the mapping requires that. |
| `location_company` | string or `null` | No | Location/company value. |
| `detailed_description` | string or `null` | No | Detailed change description. |
| `company` | string or `null` | No | Company associated with the change. |
| `support_organization` | string or `null` | No | Support organization. |
| `support_group_name` | string or `null` | No | Support group. |
| `change_nature` | string or `null` | No | Change nature classification. |
| `nature_of_change` | string or `null` | No | More specific change classification. |
| `application_infrastructure` | string or `null` | No | Application/infrastructure classification. |
| `downtime_required` | string or `null` | No | Downtime requirement value. |
| `service_ci` | string or `null` | No | Related service/CI identifier. |
| `description` | string or `null` | No | Short description. |
| `environment` | string or `null` | No | Target environment. |
| `scheduled_start_at` | date-time string or `null` | No | Planned start timestamp. |
| `scheduled_end_at` | date-time string or `null` | No | Planned end timestamp; if both are supplied, it must be later than the start. |
| `source_payload` | object or `null` | No | Additional source-system fields. |
| `created_at`, `updated_at` | date-time strings | Response only | Database-managed timestamps. |

### 4.2 Change request JSON

```json
{
  "id": "change-001",
  "source_change_id": "CHG-SIM-001",
  "first_name": "Test",
  "last_name": "User",
  "status": "Draft",
  "impact": "2000",
  "urgency": "4000",
  "location_company": "Example Company",
  "detailed_description": "Apply an approved operating system security update to the target server.",
  "company": "Example Company",
  "support_organization": "Example Infrastructure Support",
  "support_group_name": "Example Server Support",
  "change_nature": "Security Patch",
  "nature_of_change": "Operating System Update",
  "application_infrastructure": "Infrastructure",
  "downtime_required": "Pending Approval",
  "service_ci": "CI-SERVER-001",
  "description": "Simulated security patch change request",
  "environment": "UAT",
  "scheduled_start_at": "2026-11-02T20:00:00Z",
  "scheduled_end_at": "2026-11-02T22:00:00Z",
  "source_payload": {
    "is_simulated": true,
    "note": "Synthetic example; values require mapping to the actual BMC Helix ITSM form."
  }
}
```

### 4.3 ITSM worklog

| Field | JSON type | Description |
|---|---|---|
| `id` | string in fixture / integer in database response | Worklog identity. |
| `source_worklog_id` | string or `null` | External worklog identifier. |
| `source_change_id` | string in fixture input | External change identifier used to associate the worklog with a change. |
| `change_id` | integer in database response | Internal change table ID. |
| `description` | string or `null` | Worklog text. |
| `submitter` | string or `null` | Person/system that submitted the worklog. |
| `worklog_type` | string or `null` | Worklog category. |
| `created_at` | date-time string | Creation timestamp. |
| `source_payload` | object or `null` | Extra source fields. |

```json
{
  "id": "worklog-001",
  "source_worklog_id": "WL-SIM-0001",
  "source_change_id": "CHG-SIM-001",
  "description": "Simulated worklog: security patch change reviewed for testing.",
  "submitter": "simulator",
  "worklog_type": "Work Info",
  "created_at": "2026-10-26T08:30:00Z",
  "source_payload": {
    "status": "Recorded",
    "is_simulated": true
  }
}
```

### 4.4 Change history

The history response schema contains `id`, `change_id`, `action`, `previous_status`, `new_status`, `details`, `source_payload`, and `created_at`. `change_id` is an internal database ID in the response, not the external `source_change_id`.

```json
{
  "id": 1,
  "change_id": 1,
  "action": "status_changed",
  "previous_status": "Draft",
  "new_status": "Scheduled",
  "details": "Status updated by simulator test.",
  "source_payload": {"is_simulated": true},
  "created_at": "2026-10-26T08:35:00Z"
}
```

---

## 5. Red Hat Satellite data

### 5.1 Host (`satellite_hosts`)

| Field | JSON type | Required on create? | Description |
|---|---|---:|---|
| `id` | string in fixture / integer in database response | No | Simulator/database identity. |
| `source_host_id` | string | **Yes** | External Satellite host ID; nonblank, maximum 100 characters. |
| `name` | string | **Yes** | Host name; nonblank, maximum 255 characters. |
| `ip_address` | string or `null` | No | Host IP address. |
| `operating_system` | string or `null` | No | OS description. |
| `organization_id` | integer or `null` | No | Satellite organization ID. |
| `location_id` | integer or `null` | No | Satellite location ID. |
| `source_payload` | object or `null` | No | Extra host metadata. |
| `created_at`, `updated_at` | date-time strings | Response only | Database-managed timestamps. |

```json
{
  "id": "satellite-host-001",
  "source_host_id": "satellite-host-001",
  "name": "server01.example.local",
  "ip_address": "192.0.2.10",
  "operating_system": "Red Hat Enterprise Linux 9",
  "organization_id": 1,
  "location_id": 1,
  "source_payload": {
    "os_version": "9.8",
    "environment": "UAT",
    "status": "Managed",
    "lifecycle_environment": "Library",
    "content_view": "Default Organization View",
    "organization": "Example Organization",
    "location": "Default Location",
    "last_checkin": "2026-10-25T08:30:00Z",
    "is_simulated": true
  }
}
```

### 5.2 Job template (`satellite_job_templates`)

| Field | JSON type | Description |
|---|---|---|
| `id` | string in fixture / integer in database response | Internal template identity. |
| `source_template_id` | string | External Satellite template ID. |
| `name` | string | Template name. |
| `description` | string or `null` | Template description. |
| `template_type` | string or `null` | Application-defined template category. |
| `input_schema` | object or `null` | Optional JSON Schema describing accepted `inputs`. |
| `source_payload` | object or `null` | Additional provider metadata. |
| `created_at` | date-time string | Database-managed creation timestamp. |

```json
{
  "id": "job-template-001",
  "source_template_id": "job-template-001",
  "name": "Simulated Package Update",
  "description": "Simulates a package-update workflow for local testing. No remote command is executed.",
  "template_type": "package_update",
  "input_schema": {
    "type": "object",
    "properties": {
      "package_name": {"type": "string", "description": "Package to check or update."},
      "check_mode": {"type": "boolean", "default": true, "description": "Simulate the operation without applying changes."}
    },
    "required": ["package_name"],
    "additionalProperties": false
  },
  "source_payload": {"provider": "json", "enabled": true, "supports_check_mode": true, "is_simulated": true}
}
```

### 5.3 Job launch request

The launch request accepts external source identifiers. The service resolves those identifiers to internal database records when using the relational database provider.

| Field | JSON type | Required? | Validation |
|---|---|---:|---|
| `template_id` | string | **Yes** | Nonblank, maximum 100 characters; external template ID. |
| `host_ids` | array of strings | **Yes** | 1–100 host IDs; entries must be nonblank and unique. |
| `inputs` | object | No | Defaults to `{}`. Input fields should conform to the template's `input_schema` when one is defined. |

```json
{
  "template_id": "job-template-001",
  "host_ids": ["satellite-host-001", "satellite-host-002"],
  "inputs": {
    "package_name": "openssl",
    "check_mode": true
  }
}
```

### 5.4 Job run (`satellite_job_runs`)

| Field | JSON type | Description |
|---|---|---|
| `id` | string in JSON fixture / integer in database response | Internal job-run identity. |
| `source_invocation_id` | string or `null` | External Satellite invocation ID, when available. |
| `template_id` | integer in database response | Internal `satellite_job_templates.id` foreign key. Fixture providers may use the external string under `job_template_id`. |
| `job_template_id` | string in the JSON fixture provider | External/template fixture ID used by the JSON simulation format. |
| `host_ids` | array of strings in the JSON fixture provider | External/fixture host IDs. Database job-run responses expose per-host results separately. |
| `status` | string | Job state, e.g. `pending`, `running`, `completed`, `failed`, `cancelled`. |
| `inputs` | object | Inputs supplied for the run. |
| `started_at` | date-time string or `null` | Start timestamp. |
| `completed_at` or `finished_at` | date-time string or `null` | Completion timestamp; property name depends on provider/schema format. |
| `result_summary` | string or `null` in fixture format | Human-readable overall result summary. |
| `error_message` | string or `null` in fixture format | Error details when a run fails. |
| `change_id` | string or `null` in fixture format | Optional related external ITSM change ID. |
| `source_payload` | object or `null` in database response | Additional provider response. |
| `created_at` | date-time string in database response | Database-managed creation timestamp. |

Example in the JSON fixture-provider format:

```json
{
  "id": "job-run-001",
  "job_template_id": "job-template-001",
  "job_template_name": "Simulated Package Update",
  "host_ids": ["satellite-host-001"],
  "status": "completed",
  "started_at": "2026-10-25T10:00:00Z",
  "finished_at": "2026-10-25T10:05:00Z",
  "result_summary": "Simulated package update completed successfully. No remote command was executed.",
  "inputs": {"package_name": "openssl", "check_mode": true},
  "is_simulated": true,
  "change_id": "CHG-SIM-001",
  "error_message": null
}
```

### 5.5 Per-host job result (`satellite_job_host_results`)

| Field | JSON type | Description |
|---|---|---|
| `id` | string in fixture / integer in database response | Result identity. |
| `job_run_id` | string in fixture / integer in database response | Parent job-run reference. |
| `host_id` | string in fixture / integer in database response | Related host reference. |
| `status` | string | Per-host outcome, e.g. `pending`, `success`, `failed`, `cancelled`. |
| `result_text` | string or `null` in database response | Normalized result text. |
| `stdout` | string in fixture format | Standard output text. |
| `stderr` | string in fixture format | Standard error text. |
| `exit_code` | integer or `null` in fixture format | Exit code if available. |
| `started_at` | date-time string or `null` | Start timestamp. |
| `completed_at` or `finished_at` | date-time string or `null` | Completion timestamp. |
| `is_simulated` | boolean in fixture format | `true` indicates no real remote command was executed. |
| `source_payload` | object or `null` in database response | Provider-specific result payload. |

```json
{
  "id": "job-host-result-001",
  "job_run_id": "job-run-001",
  "host_id": "satellite-host-001",
  "status": "success",
  "started_at": "2026-10-25T10:00:00Z",
  "finished_at": "2026-10-25T10:05:00Z",
  "exit_code": 0,
  "stdout": "SIMULATION: package update check completed. No remote command was executed.",
  "stderr": "",
  "is_simulated": true
}
```

---

## 6. Source-system fields vs normalized fields

The payload received from a vendor API can have different names and nesting from the normalized schema documented here. The provider layer should map the source response into the canonical field names before handing it to the service layer.

| Source/source-system concept | Normalized field example | Notes |
|---|---|---|
| Tenable vulnerability/plugin identity | `source_finding_id`, `plugin_id`, `plugin_name` | Preserve the vendor ID separately from the simulator/database ID. |
| CMDB class instance ID | `source_instance_id` | Use one stable external ID for matching the CI across imports. |
| CMDB host name | `ci_name`, `dns_host_name` | Confirm exact source attribute names in the actual class/schema. |
| BMC change request ID | `source_change_id` | Store source-specific form values in `source_payload` if they have no mapped column. |
| Satellite host ID | `source_host_id` | Keep external IDs as strings at the integration boundary. |
| Satellite template ID | `source_template_id` | The relational service may separately use an internal integer primary key. |
| Satellite invocation/job ID | `source_invocation_id` | Use `null` until an external job has actually been created. |

Do not assume field names or enum values are identical across Tenable, BMC Helix, and Satellite versions. Validate mappings with representative API responses from the target environment.

## 7. JSON fixture validation checklist

Before loading or committing fixture data, verify:

1. Each fixture file contains a JSON array of objects.
2. Each object has a nonblank `id` and fixture IDs are unique within that file.
3. Every record has the required integration-specific source ID (`source_finding_id`, `source_instance_id`, `source_change_id`, `source_host_id`, or `source_template_id`) where applicable.
4. Timestamps are valid ISO 8601 strings and timezone offsets are explicit.
5. Scores and ports are JSON numbers; IDs are strings when they represent external identifiers.
6. `source_payload` and `inputs` are JSON objects, not JSON-encoded strings.
7. Satellite job runs reference existing templates and hosts; per-host results reference an existing run and host.
8. ITSM scheduled end time is later than scheduled start time when both are supplied.
9. All fixture rows are synthetic unless deliberately replaced with approved test data.
10. API-mode mapping has been tested separately before switching any `*_PROVIDER` setting from `json` to `api`.

## 8. Important implementation caveat

The JSON fixture provider and the SQLAlchemy-backed API schemas are not identical serialization formats in every area—most notably Satellite job runs/results, which use string fixture IDs and fixture-specific fields such as `finished_at`, `stdout`, and `exit_code`, while the database response schemas use integer internal IDs and normalized fields such as `completed_at` and `result_text`. Keep this difference explicit in adapters and tests rather than assuming the same object can be used unchanged by both providers.
