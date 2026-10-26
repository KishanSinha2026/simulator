"""Script to generate the VPM360 Database Tables and Schemas Word document."""

import datetime
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from app.db.base import Base
import app.models
from app.main import app


def set_cell_background(cell, hex_color: str):
    """Set the background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set padding for a cell in dxa (1 pt = 20 dxa)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tc_pr.append(tc_mar)


def format_table_headers(table, col_names, col_widths=None):
    """Format table header row with corporate styling."""
    hdr_cells = table.rows[0].cells
    for i, name in enumerate(col_names):
        hdr_cells[i].text = name
        set_cell_background(hdr_cells[i], "1A365D")  # Deep Navy
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=140, right=140)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9.5)
            run.font.name = "Calibri"

    # Set column widths if provided
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                if i < len(row.cells):
                    row.cells[i].width = Inches(w)


def style_table_rows(table, col_widths=None):
    """Style data rows with alternating colors and clean typography."""
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r_idx, row in enumerate(table.rows[1:], start=1):
        bg_color = "F7FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, cell in enumerate(row.cells):
            set_cell_background(cell, bg_color)
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9)
                    run.font.name = "Calibri"
                    run.font.color.rgb = RGBColor(45, 55, 72)
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                if i < len(row.cells):
                    row.cells[i].width = Inches(w)


def add_custom_heading(doc, text: str, level: int):
    """Add styled heading."""
    h = doc.add_heading(text, level=level)
    run = h.runs[0]
    run.font.name = "Calibri"
    if level == 1:
        run.font.color.rgb = RGBColor(26, 54, 93)  # #1A365D
        run.font.size = Pt(18)
        run.bold = True
        h.paragraph_format.space_before = Pt(18)
        h.paragraph_format.space_after = Pt(6)
    elif level == 2:
        run.font.color.rgb = RGBColor(43, 108, 176)  # #2B6CB0
        run.font.size = Pt(14)
        run.bold = True
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(4)
    elif level == 3:
        run.font.color.rgb = RGBColor(74, 85, 104)  # #4A5568
        run.font.size = Pt(11.5)
        run.bold = True
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(3)
    return h


def main():
    doc = Document()

    # Set page margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # -------------------------------------------------------------
    # Cover / Document Title
    # -------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(24)
    title_p.paragraph_format.space_after = Pt(4)
    title_run = title_p.add_run("VPM360 Enterprise Integration Specification")
    title_run.font.name = "Calibri"
    title_run.font.size = Pt(26)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(26, 54, 93)

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(16)
    sub_run = sub_p.add_run("Database Tables, Column Schemas, Pydantic DTOs & API/JSON Routes")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(14)
    sub_run.font.color.rgb = RGBColor(43, 108, 176)

    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_after = Pt(24)
    meta_run = meta_p.add_run(
        f"Target Database: postgresql+psycopg://appuser:***@localhost:5433/appdb\n"
        f"BRD Reference: VPM360 IndusInd Enterprise BRD, HLD & TDD v1.0\n"
        f"Date: {datetime.date.today().strftime('%B %d, %Y')} | Version: 1.0.0 Enterprise"
    )
    meta_run.font.size = Pt(10)
    meta_run.font.italic = True
    meta_run.font.color.rgb = RGBColor(113, 128, 150)

    doc.add_page_break()

    # -------------------------------------------------------------
    # Executive Summary
    # -------------------------------------------------------------
    add_custom_heading(doc, "1. Executive Summary & Architecture Overview", 1)
    
    p = doc.add_paragraph(
        "This technical document provides the complete specification of database tables, column definitions, "
        "constraints, Pydantic validation schemas, and REST API/JSON provider routes developed for the VPM360 "
        "IndusInd Enterprise platform. The solution unifies four enterprise systems into an automated, "
        "idempotent vulnerability and patch remediation workflow:"
    )
    p.runs[0].font.size = Pt(10)

    bullet_points = [
        ("Tenable Vulnerability Management:", "Ingests and correlates vulnerability findings with CVSS v3 precedence over v4 (never v2), scans metadata, and retains full 54 BRD Appendix A fields in source_payload."),
        ("BMC Helix CMDB:", "Performs exact IP address correlation across Servers (Appendix C.1 - 22 fields), Middleware (Appendix C.2 - 19 fields), and Databases (Appendix C.3 - 14 fields), returning BRD-mandated execution outcomes (MATCHED, CMDB_NOT_FOUND, AMBIGUOUS_MATCH, CMDB_CI_INACTIVE)."),
        ("BMC Helix ITSM & ISTM Alias:", "Manages change requests, worklogs, and audit history conforming to BRD Appendix D QA change request specifications (19 fields). Full route aliases are mounted identically under both /api/v1/itsm and /api/v1/istm."),
        ("Red Hat Satellite 6.9:", "Supports host inventory, Ansible/Remote execution job templates, simulated and live job execution with static host selection, and job cancellation.")
    ]
    for b_title, b_desc in bullet_points:
        bp = doc.add_paragraph(style='List Bullet')
        r1 = bp.add_run(b_title + " ")
        r1.bold = True
        r1.font.size = Pt(9.5)
        r2 = bp.add_run(b_desc)
        r2.font.size = Pt(9.5)

    p_arch = doc.add_paragraph(
        "Dual-Mode Architecture: Every integration operates seamlessly in both API/PostgreSQL Database mode "
        "(persisted ACID storage with SQLAlchemy 2.0 and psycopg3) and JSON Provider mode "
        "(in-memory fixture preview and file-based mutation via JSON fixtures)."
    )
    p_arch.runs[0].font.size = Pt(10)

    # -------------------------------------------------------------
    # Database Tables Reference
    # -------------------------------------------------------------
    add_custom_heading(doc, "2. Database Tables & Column Schema Catalog", 1)

    table_descriptions = {
        "tenable_scans": "Stores Tenable scan runs, execution status, completion timestamps, and full scanResult source payload.",
        "tenable_findings": "Stores normalized Tenable vulnerability findings with CVSS v3/v4 score precedence and 54-field payload snapshot.",
        "tenable_finding_cves": "Associates CVE identifiers to specific vulnerability findings in a 1-to-many relationship.",
        "cmdb_servers": "Stores BMC Helix CMDB ComputerSystem/Server CIs (22 fields from BRD Appendix C.1) used as primary patch correlation targets.",
        "cmdb_middleware": "Stores BMC Helix CMDB Middleware CIs (19 fields from BRD Appendix C.2) linked to server infrastructure.",
        "cmdb_databases": "Stores BMC Helix CMDB Database CIs (14 fields from BRD Appendix C.3) representing database instances.",
        "cmdb_relationships": "Represents CMDB CI-to-CI dependency relationships (e.g. Runs On, Hosted By, Impacts).",
        "itsm_changes": "Stores BMC Helix ITSM Change Requests implementing all 19 BRD Appendix D QA Change fields.",
        "itsm_worklogs": "Stores time-stamped worklog notes and activity updates associated with change requests.",
        "itsm_change_history": "Maintains an immutable historical audit log of status transitions and approvals for ITSM changes.",
        "satellite_hosts": "Maintains Red Hat Satellite 6.9 registered host inventory targets for patch deployment.",
        "satellite_job_templates": "Stores Satellite Remote Execution and Ansible playbook job templates.",
        "satellite_job_runs": "Tracks execution instances of Satellite remediation playbooks with status lifecycle.",
        "satellite_job_host_results": "Stores per-host execution outcomes, exit codes, and stdout/stderr logs for each job run.",
        "sync_runs": "Audit table tracking background synchronization cycles, records processed, and failure counts.",
        "mock_request_logs": "Diagnostics log recording incoming integration API payloads and external HTTP interactions."
    }

    modules = [
        ("2.1 Tenable Integration Tables", ["tenable_scans", "tenable_findings", "tenable_finding_cves"]),
        ("2.2 BMC Helix CMDB Tables", ["cmdb_servers", "cmdb_middleware", "cmdb_databases", "cmdb_relationships"]),
        ("2.3 BMC Helix ITSM & ISTM Tables", ["itsm_changes", "itsm_worklogs", "itsm_change_history"]),
        ("2.4 Red Hat Satellite Tables", ["satellite_hosts", "satellite_job_templates", "satellite_job_runs", "satellite_job_host_results"]),
        ("2.5 Platform Audit & Synchronization Tables", ["sync_runs", "mock_request_logs"])
    ]

    metadata_tables = {t.name: t for t in Base.metadata.sorted_tables}

    for mod_title, tbl_names in modules:
        add_custom_heading(doc, mod_title, 2)
        for tbl_name in tbl_names:
            if tbl_name not in metadata_tables:
                continue
            table_obj = metadata_tables[tbl_name]
            add_custom_heading(doc, f"Table: {tbl_name}", 3)

            p_desc = doc.add_paragraph()
            r_desc = p_desc.add_run(f"Description: {table_descriptions.get(tbl_name, 'Database table')}")
            r_desc.font.size = Pt(9.5)
            r_desc.font.italic = True

            # Create table
            t = doc.add_table(rows=1, cols=5)
            format_table_headers(
                t,
                ["Column Name", "Type", "Null?", "Key / Constraints", "Description / Notes"],
                col_widths=[1.5, 1.2, 0.6, 1.5, 2.2]
            )

            for col in table_obj.columns:
                row = t.add_row()
                cells = row.cells
                cells[0].text = col.name
                cells[1].text = str(col.type)
                cells[2].text = "YES" if col.nullable else "NO"

                constraints = []
                if col.primary_key:
                    constraints.append("PRIMARY KEY")
                if col.unique:
                    constraints.append("UNIQUE")
                if col.foreign_keys:
                    for fk in col.foreign_keys:
                        constraints.append(f"FK -> {fk.target_fullname}")
                if col.index:
                    constraints.append("INDEX")
                cells[3].text = ", ".join(constraints) if constraints else "-"

                # Description generator based on column name and table
                desc = "-"
                cname = col.name
                if cname == "id":
                    desc = "Primary key surrogate ID (serial integer)"
                elif cname.startswith("source_"):
                    desc = f"External system unique identifier from {tbl_name.split('_')[0].upper()}"
                elif cname == "created_at":
                    desc = "Timestamp when the record was persisted (server default NOW())"
                elif cname == "updated_at":
                    desc = "Timestamp when the record was last modified"
                elif cname == "source_payload":
                    desc = "Raw JSONB snapshot retaining full source attributes and metadata"
                elif "cvss" in cname:
                    desc = "CVSS vulnerability severity base score (0.0 to 10.0)"
                elif cname == "status":
                    desc = "Current lifecycle or execution status"
                elif cname == "ip_address":
                    desc = "IPv4/IPv6 address used for CMDB CI correlation"
                elif cname == "correlation_outcome":
                    desc = "BRD 4.3 rule outcome: MATCHED, CMDB_NOT_FOUND, etc."
                elif cname == "inputs":
                    desc = "Playbook execution input parameters (JSONB)"
                elif cname == "job_run_id":
                    desc = "Reference to parent Satellite job run"
                elif cname == "host_id":
                    desc = "Reference to target Satellite host"
                cells[4].text = desc

            style_table_rows(t, col_widths=[1.5, 1.2, 0.6, 1.5, 2.2])
            doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # Pydantic Schemas Matrix
    # -------------------------------------------------------------
    doc.add_page_break()
    add_custom_heading(doc, "3. Pydantic Validation & Transfer Schemas (DTOs)", 1)
    
    p_schema_intro = doc.add_paragraph(
        "All incoming payloads and outgoing API responses are strictly validated through Pydantic v2 models. "
        "Extra inputs are forbidden (`extra='forbid'`) to guarantee contract fidelity, while `from_attributes=True` "
        "allows direct serialization from SQLAlchemy ORM entities."
    )
    p_schema_intro.runs[0].font.size = Pt(10)

    pydantic_modules = [
        ("3.1 Tenable Pydantic Schemas", [
            ("TenableFindingCreate", "Request body for manually creating or simulating vulnerability findings.", "plugin_id (int), source_finding_id, ip_address, severity, synopsis, description, cvss_v3_base_score, cvss_v4_base_score, port, repository, protocol"),
            ("TenableFindingResponse", "Response representation of a persisted vulnerability finding.", "id (int), actionable (computed bool), source_finding_id, plugin_id, plugin_name, severity, cvss_v3_base_score, cvss_v4_base_score, first_discovered, last_observed, created_at, updated_at"),
            ("TenableFindingListResponse", "Paginated list response container for findings.", "items (list[TenableFindingResponse]), total (int), limit (int), offset (int), has_more (bool)"),
            ("TenableScanCreate", "Request schema for creating a Tenable scan record.", "source_scan_id (str), name (str), status (str), started_at, completed_at, source_payload (dict)"),
            ("TenableScanResponse", "Response schema for a persisted Tenable scan.", "id (int), source_scan_id, name, status, started_at, completed_at, source_payload, created_at, updated_at"),
            ("TenableScanListResponse", "Paginated list container for Tenable scans.", "items (list[TenableScanResponse]), total, limit, offset, has_more"),
            ("TenableImportResponse", "Summary response returned by provider import endpoint.", "records_received, created, updated, skipped_without_source_identity, informational_records_retained, errors, source_offset, source_limit")
        ]),
        ("3.2 CMDB Pydantic Schemas", [
            ("CMDBServerCreate / Update", "Request schemas for creating/modifying server and OS CIs (Appendix C.1).", "source_instance_id (required), ci_name, dns_host_name, ip_address, application_name, asset_owner, environment, production_status, operating_system, risk_classification, target_date"),
            ("CMDBServerResponse / List", "Response schema and paginated list for server CIs.", "id (int), source_instance_id, ci_name, ip_address, production_status, operating_system, created_at, updated_at"),
            ("CMDBMiddlewareCreate / Response", "Schema for middleware CIs (Appendix C.2 - 19 fields).", "source_instance_id, middleware_name, version, hostname, ip_address, application_name, recommended_version, latest_patch_release_date, target_date"),
            ("CMDBDatabaseCreate / Response", "Schema for database CIs (Appendix C.3 - 14 fields).", "source_instance_id, database_name, version, hostname, ip_address, db_type, asset_owner, last_patch_updated_at, target_date"),
            ("CMDBRelationshipCreate / Response", "Schema for CMDB CI-to-CI graph relationships.", "source_relationship_id, source_ci_type, source_ci_id, target_ci_type, target_ci_id, relationship_type"),
            ("CMDBLookupResponse", "Response schema for BRD 4.3 IP correlation outcome.", "ip_address, correlation_outcome (MATCHED, CMDB_NOT_FOUND, AMBIGUOUS_MATCH, CMDB_CI_INACTIVE), matched_servers (list), message"),
            ("CMDBImportResponse", "Summary schema for CMDB provider import.", "servers_imported, middleware_imported, databases_imported, relationships_imported, total_imported")
        ]),
        ("3.3 ITSM / ISTM Pydantic Schemas", [
            ("ITSMChangeCreate / Update", "Request schemas for creating/updating change requests (Appendix D - 19 fields).", "source_change_id (required), first_name, last_name, status, impact, urgency, company, support_organization, change_nature, application_infrastructure, downtime_required, service_ci, description, environment"),
            ("ITSMChangeResponse / List", "Response schema and paginated list for change requests.", "id (int), source_change_id, description, status, service_ci, environment, scheduled_start_at, scheduled_end_at, created_at, updated_at"),
            ("ITSMWorklogCreate / Response", "Schema for adding/retrieving worklog notes.", "description (required), submitter, worklog_type, source_worklog_id, change_id (int), created_at"),
            ("ITSMChangeHistoryResponse", "Schema representing change status transitions.", "id (int), change_id, old_status, new_status, changed_by, notes, created_at"),
            ("ITSMImportResponse", "Summary schema for ITSM provider import.", "changes_imported, worklogs_imported, total_imported")
        ]),
        ("3.4 Satellite Pydantic Schemas", [
            ("SatelliteHostCreate / Response", "Request and response schemas for managed host targets.", "source_host_id, name, ip_address, operating_system, organization_id, location_id, source_payload"),
            ("SatelliteJobTemplateCreate / Response", "Schema for Remote Execution / Ansible job templates.", "source_template_id, name, description, template_type, input_schema, source_payload"),
            ("SatelliteJobLaunchRequest", "Request schema to launch/simulate a remediation job.", "template_id (str), host_ids (list[str] non-empty), inputs (dict)"),
            ("SatelliteJobRunResponse / List", "Response representation of a job invocation.", "id (int), source_invocation_id, template_id, status, inputs, started_at, completed_at, source_payload, created_at"),
            ("SatelliteJobHostResultResponse", "Per-host outcome schema for job execution.", "id, job_run_id, host_id, status, result_text, exit_code, stdout, stderr, finished_at"),
            ("SatelliteJobCancelRequest", "Request schema to cancel a pending job.", "reason (str | None)")
        ])
    ]

    for pmod_title, schemas in pydantic_modules:
        add_custom_heading(doc, pmod_title, 2)
        st = doc.add_table(rows=1, cols=3)
        format_table_headers(st, ["Schema Name", "Role & Usage", "Key Attributes & Constraints"], col_widths=[2.0, 2.2, 2.8])
        for s_name, s_role, s_attrs in schemas:
            row = st.add_row()
            row.cells[0].text = s_name
            row.cells[1].text = s_role
            row.cells[2].text = s_attrs
        style_table_rows(st, col_widths=[2.0, 2.2, 2.8])
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # Complete Routes Matrix (All 57 endpoints)
    # -------------------------------------------------------------
    doc.add_page_break()
    add_custom_heading(doc, "4. Complete API & JSON Provider Route Catalog", 1)

    p_route_intro = doc.add_paragraph(
        "The application registers 57 OpenAPI endpoints across all four enterprise integrations. "
        "The matrix below categorizes each endpoint by its operational target: PostgreSQL Database (ACID Storage) "
        "or Active Integration Provider (JSON Fixtures / External Mock)."
    )
    p_route_intro.runs[0].font.size = Pt(10)

    # Collect routes from FastAPI app
    route_list = []
    openapi_paths = app.openapi().get("paths", {})
    for path, methods in openapi_paths.items():
        if not path.startswith("/api/v1"):
            continue
        for method, details in methods.items():
            summary = details.get("summary") or details.get("description") or "-"
            # Determine provider mode
            if "/provider" in path or path.endswith("/correlate/{ip_address}"):
                mode = "Provider / JSON Data"
            else:
                mode = "PostgreSQL Database"
            route_list.append((method.upper(), path, summary, mode))

    route_list.sort(key=lambda x: (x[1], x[0]))

    rt = doc.add_table(rows=1, cols=4)
    format_table_headers(rt, ["Method", "Endpoint Path", "Operational Mode", "Description / Function"], col_widths=[0.9, 2.5, 1.4, 2.2])

    for method, path, summary, mode in route_list:
        row = rt.add_row()
        row.cells[0].text = method
        row.cells[1].text = path
        row.cells[2].text = mode
        row.cells[3].text = summary.split("\n")[0][:100]

    style_table_rows(rt, col_widths=[0.9, 2.5, 1.4, 2.2])

    # Save document
    filename = "VPM360_Database_Tables_and_Schemas.docx"
    doc.save(filename)
    print(f"Successfully generated {filename}")


if __name__ == "__main__":
    main()
