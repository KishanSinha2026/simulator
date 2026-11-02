# BRD integration endpoint coverage

This inventory compares the VPM360 routes in `app/api/v1`, stored integration
records, and external routes used by providers with the BRD in
`data/extracted_doc_summary.txt`. Paths on a provider are called by VPM360;
they are not public VPM360 routes.

The workbook [`VPM360_BRD_API_Backend_Mapping.xlsx`](VPM360_BRD_API_Backend_Mapping.xlsx)
contains the BRD endpoint map, all 59 current VPM360 route declarations,
fixture-to-PostgreSQL JSON equality results, and unresolved BRD gaps.

## Connector connection checks — BRD 3.1

Each connector exposes `GET /api/v1/{connector}/connection` for Tenable,
Squad1, CMDB, ITSM, Satellite, SCCM, and Ansible. API mode performs a
read-only probe using that provider's configured endpoint and credentials.
JSON mode verifies that local fixture data is readable and returns
`status: fixture`, `connected: false`; it does not claim that the vendor is
reachable. The response never includes credentials or source records. The
BRD asks for connection health, last test, and a Test Connection control. Each result is stored in PostgreSQL `integration_connection_checks`, and the response returns the durable `history_id`. The BRD does not prescribe these endpoint paths. `/api/v1/health` and
`/api/v1/ready` remain VPM360 application/database health checks.

## Tenable — BRD 4.1

The public API exposes `GET /api/v1/tenable/findings`,
`GET /api/v1/tenable/findings/{finding_id}`, `GET /api/v1/tenable/scans`,
and `POST /api/v1/tenable/import`. The API provider supports both BRD source
paths, `/rest/scanResult` and `/rest/analysis`. The BRD leaves the HTTP verbs,
analysis request parameter/body, paging, authentication, and successful
response shape for client confirmation; those values remain configuration,
not inferred defaults. Original source JSON is retained in `source_payload`.

## CMDB — BRD 4.3

The public API exposes server inventory, IP correlation, middleware/database
inventory, relationships, and import routes under `/api/v1/cmdb`. The provider
supports the supplied BMC routes: `POST /api/jwt/login`,
`GET /api/cmdb/v1.0/instances/{datasetId}/BMC.CORE/BMC_IPEndpoint`,
`GET /api/cmdb/v1.0/graphwalk`,
`GET /api/cmdb/v1.0/instances/{datasetId}/BMC.CORE/BMC_ComputerSystem/{instanceId}`,
and `GET /api/cmdb/v1.0/attributes/BMC.CORE/BMC_ComputerSystem`.
Writeback remains disabled until the bank confirms dataset, class, fields,
and write timing as required by the BRD.

## ITSM — BRD 4.4

The public API exposes change list/create/read/update and worklog
list/create routes under `/api/v1/itsm`, plus import. The live provider supports
JWT login, the configured create form, and a candidate read form. The BRD marks
the exact read form/fields, approval and maintenance-window interface, update
route, worklog interface, and closure action as pending client confirmation.
Those operations are not fabricated as live Helix calls; local VPM360 routes
must not be mistaken for confirmation that a corresponding Helix API is
available.

## Squad1 — BRD 4.2

Vulnerability list/detail/create, exception list, and import routes are
present. The API accepts the BRD `severity` field while persisting the
normalized `risk_rating`, and responses expose both names. Fixture records retain all 82 exact Appendix B source keys under `source_payload.source_record`; the first record uses the sanitized Appendix E sample. Live URL, method, response and lifecycle semantics remain subject to Squad1/client confirmation. The exception
response includes `is_expired`; the exception list returns only records with
a non-expired end date. Ansible launch blocks exact target names with active
exceptions, while the Satellite and SCCM simulated workflows mark matching
targets skipped.

## Satellite — BRD 4.5

All seven public workflow routes are present under `/api/v1/satellite`: host
list (S1), approved template list (S2), job launch (S3), job status (S4),
per-host result (S5), per-host raw output (S6), and cancellation (S7). The API
provider implements the corresponding reads and cancellation; the S6
raw-output provider call was added in this change. The provider has a launch
method, but the public S3 route does not call it. Satellite 6.9 route aliases, template inputs,
host selection, and response/output formats still require validation against
the client instance. In particular, S3 currently records a simulated run in
the service; it does not execute a remote patch job. Do not treat it as live
execution until the BRD approval, target, and template controls are wired and
validated.

## Ansible Automation Platform / AWX — BRD 4.7

The BRD requires inventory host listing, ad-hoc command schema discovery,
approved script execution, command status, per-host events, stdout evidence, and
cancellation. The current `/api/v1/ansible` integration instead lists job
templates and launches `job_templates/{id}/launch/`; it does not implement the
BRD's `inventories/{id}/ad_hoc_commands` and events/stdout contract. It stores
launch/status payloads in `ansible_job_runs`; imported template records and the
complete source JSON are stored in `ansible_job_templates.source_payload`.
Template listing supports database pagination and imports fixtures when the
table is empty. Inventory hosts and normalized per-host event/evidence records
are not persisted. Therefore template/job JSON retention exists, but execution
and per-host data requirements do not yet match BRD 4.7. Confirm the Controller
version, inventory IDs, permissions, and approved scripts before implementing
the live contract.

## SCCM — BRD 4.6 and 8.5.5

The public device, collection, deployment, job history, and import endpoints
are present. In fixture mode, import persists device, collection, deployment,
deployment-run, and per-asset records to PostgreSQL with full source JSON. The
AdminService provider currently implements inventory reads;
`POST /api/v1/sccm/jobs` records a local simulated run rather than submitting a
remote SCCM deployment. The SCCM device schema exposes `client_version` and
BRD-compatible `source_device_id` / `hostname` aliases. Missing or
inactive/non-client devices are no longer reported as successful targets;
active Squad1 exceptions mark matching targets skipped.
The BRD-derived README does not contain a concrete AdminService deployment
launch route or payload for live execution, so this remains an implementation
gap pending that contract.

## Database

The integration models preserve unmapped source fields in `source_payload`.
The 22 server, 19 middleware, and 14 database fields are mapped to normalized
attributes where the BRD supplies a clear meaning. Middleware `Username` is
now a dedicated nullable column, added by Alembic revision
`a74c2e6105f1`; server `Aging` is a response field derived in calendar days
from `Last Patched Date`. The initial Alembic revision creates the base VPM360
tables for a fresh database; additive revisions create later integration
tables and columns. Middleware and
database CMDB class names are not specified in the BRD, so API mode requires
the CMDB team to supply `CMDB_MIDDLEWARE_CLASS` and `CMDB_DATABASE_CLASS`.
Apply migrations only through the configured database migration workflow.

Migration `c1a9d8402f7b` adds Ansible job history, `e4f6a8b0c2d4` adds stored
Ansible job templates, and `e7d9c2b1456a` adds the
normalized SCCM `client_version` field (backfilled from retained payloads),
`f2b74c9d1360` adds the README deployment ID and per-asset reboot status, and
`9b6f1c4e8a20` makes `reboot_pending` a required boolean. The checked database
is at `e4f6a8b0c2d4` and includes the Ansible template table.

Fixture imports retain the complete input object in JSONB for CMDB, ITSM,
Satellite, SCCM, Squad1, and Ansible. Tenable preserves the complete scanner
finding under `source_payload.raw_record`. Satellite and SCCM demo run/result
fixtures are also imported and remain marked simulated; they are not live
execution evidence.

The ITSM changes fixture `fixtures/itsm/multichanges.json` contains 20,000 deterministic simulated change records; these are demo values, not live Helix records.

The extracted BRD source is `data/extracted_doc_summary.txt`. Its Appendix A
Tenable fields are preserved in the finding payload; Appendix B Squad1 records
are retained in full in `squad1_vulnerabilities.source_payload.source_record` (all 82 exact Appendix B keys); Appendix C
CMDB inventory fields are normalized where mapped and the original source
objects are retained; Appendix D Helix fields are mapped to normalized columns
and raw entry JSON is retained. Satellite, SCCM, and Ansible source objects are
also retained in their respective JSON/JSONB `source_payload` columns. Fixture
imports retain the complete fixture record, including any nested
`source_payload`, so normalized demo fields are not dropped. This preserves
source JSON but does not mean every BRD field has a dedicated column
or that every execution/reporting workflow is implemented. Client contracts
marked pending remain unverified.

Tenable JSON metadata uses descriptive keys: `finding_source_fields`,
`missing_finding_source_fields`, and `normalization_metadata`. Alembic
revisions `b8c2d4e6f0a1` and `c2d3e4f5a6b7` rename the earlier internal JSON
keys in existing database rows while preserving their JSON values. API
responses expose `finding_source_fields` and `scan_result_fields`.
