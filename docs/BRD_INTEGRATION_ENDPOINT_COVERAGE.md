# BRD integration endpoint coverage

This inventory compares the VPM360 routes in `app/api/v1` and the external
routes used by providers with Sections 4.1 and 4.3–4.5 of the BRD. Paths on a
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

## Database

The integration models preserve unmapped source fields in `source_payload`.
The 22 server, 19 middleware, and 14 database fields are mapped to normalized
attributes where the BRD supplies a clear meaning. Middleware `Username` is
now a dedicated nullable column, added by Alembic revision
`a74c2e6105f1`; server `Aging` is a response field derived in calendar days
from `Last Patched Date`. The initial Alembic revision was empty; it now
creates the registered VPM360 tables for a fresh database. Middleware and
database CMDB class names are not specified in the BRD, so API mode requires
the CMDB team to supply `CMDB_MIDDLEWARE_CLASS` and `CMDB_DATABASE_CLASS`.
Apply migrations only through the configured database migration workflow.
