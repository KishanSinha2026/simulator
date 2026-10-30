# BRD integration endpoint coverage

This inventory compares the VPM360 routes in `app/api/v1` and the external
routes used by providers with Sections 4.1-4.6 and 8.5.5 of the BRD. Paths on a
provider are called by VPM360; they are not public VPM360 routes.

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
normalized `risk_rating`, and responses expose both names. The exception
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

## Ansible Automation Platform / AWX

The BRD artifact available in this repository does not define a separate
Ansible contract. A dedicated `/api/v1/ansible` integration is implemented for
AWX/AAP API v2 using a bearer API key: template listing, job launch, status
refresh, cancellation, and a non-mutating connection check at
`GET /api/v1/ansible/connection`. A caller must provide exact hostnames/IPs in
`limit`; broad host patterns are rejected. Active Squad1 exceptions block a
matching launch. Executions are recorded in `ansible_job_runs`. Confirm the bank's
controller URL, approved template IDs, inventory/host limit conventions,
extra-vars contract, and approval controls before production use. The API key
must be supplied through environment configuration or a secret manager.

## SCCM — BRD 4.6 and 8.5.5

The public device, collection, deployment, job history, and import endpoints
are present. The AdminService provider currently implements inventory reads;
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

Migration `c1a9d8402f7b` adds Ansible job history, `e7d9c2b1456a` adds the
normalized SCCM `client_version` field (backfilled from retained payloads),
`f2b74c9d1360` adds the README deployment ID and per-asset reboot status, and
`9b6f1c4e8a20` makes `reboot_pending` a required boolean. The checked database
is at `9b6f1c4e8a20` and has no model/table column drift.

The repository does not contain the source BRD file itself. Per user direction,
coverage claims above use the checked-in README's BRD-derived schemas and this
endpoint inventory as the requirements basis; client-specific routes marked
pending still need their vendor API contracts before live integration can be
asserted.
