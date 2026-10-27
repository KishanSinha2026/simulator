import os
from typing import Any

import httpx
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="VPM360 Dashboard",
    page_icon="🛡️",
    layout="wide",
)


def get_api_url() -> str:
    """Read the API URL from Streamlit secrets or environment."""
    try:
        secret = st.secrets.get("API_BASE_URL", "")
    except Exception:
        secret = ""

    return str(secret or os.getenv("API_BASE_URL", "")).strip().rstrip("/")


def api_get(
    base_url: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
):
    """Send a GET request to the FastAPI backend."""
    if not base_url:
        return None, "Configure the FastAPI base URL first."

    try:
        response = httpx.get(
            f"{base_url}/{endpoint.lstrip('/')}",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json(), None

    except httpx.HTTPStatusError as exc:
        return None, f"HTTP {exc.response.status_code}: {endpoint}"

    except httpx.TimeoutException:
        return None, f"Request timed out: {endpoint}"

    except httpx.RequestError:
        return None, f"Could not connect to: {endpoint}"

    except ValueError:
        return None, f"Invalid JSON response: {endpoint}"


def get_items(
    base_url: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
):
    """Read a paginated response containing an items array."""
    data, error = api_get(base_url, endpoint, params)

    if error:
        return [], None, error

    if isinstance(data, dict) and isinstance(data.get("items"), list):
        items = [
            item for item in data["items"]
            if isinstance(item, dict)
        ]
        return items, data, None

    return [], None, f"Unexpected response format from {endpoint}"


def display_table(
    records: list[dict[str, Any]],
    columns: list[str],
):
    if not records:
        st.info("No records returned.")
        return

    dataframe = pd.DataFrame(records)
    visible_columns = [
        column for column in columns
        if column in dataframe.columns
    ]

    st.dataframe(
        dataframe[visible_columns]
        if visible_columns
        else dataframe,
        use_container_width=True,
        hide_index=True,
    )


st.title("VPM360 Integration Dashboard")
st.caption("Streamlit frontend for the existing FastAPI backend.")

with st.sidebar:
    st.header("Backend Configuration")

    api_base_url = st.text_input(
        "FastAPI Base URL",
        value=get_api_url(),
        placeholder="http://127.0.0.1:8000/api/v1",
    ).strip().rstrip("/")

    record_limit = st.selectbox(
        "Records per section",
        [25, 50, 100, 250],
        index=2,
    )

    if st.button("Refresh Dashboard"):
        st.rerun()

if not api_base_url:
    st.warning("Enter your FastAPI base URL in the sidebar.")
    st.stop()

health, health_error = api_get(
    api_base_url,
    "health",
)

if health_error:
    st.error(f"Backend health check failed: {health_error}")
else:
    st.success("Backend health endpoint responded.")

overview_tab, tenable_tab, cmdb_tab, itsm_tab, satellite_tab = st.tabs(
    ["Overview", "Tenable", "CMDB", "ITSM", "Satellite"]
)

# Overview
with overview_tab:
    st.subheader("Integration Overview")

    endpoints = [
        ("Tenable Findings", "tenable/findings"),
        ("CMDB Servers", "cmdb/servers"),
        ("ITSM Changes", "itsm/changes"),
        ("Satellite Hosts", "satellite/hosts"),
    ]

    metric_columns = st.columns(4)

    for column, (label, endpoint) in zip(
        metric_columns,
        endpoints,
    ):
        _, metadata, error = get_items(
            api_base_url,
            endpoint,
            {"limit": record_limit, "offset": 0},
        )

        if error:
            column.metric(label, "Unavailable")
            column.caption(error)
        else:
            total = (
                metadata.get("total", "Connected")
                if metadata
                else "Connected"
            )
            column.metric(label, total)

    if isinstance(health, dict):
        st.subheader("Backend Health")
        st.json(health)

# Tenable
with tenable_tab:
    st.subheader("Tenable Vulnerability Findings")

    severity = st.selectbox(
        "Severity",
        ["All", "Critical", "High", "Medium", "Low", "Info"],
    )

    ip_address = st.text_input("Filter by IP address").strip()

    params = {
        "limit": record_limit,
        "offset": 0,
    }

    if severity != "All":
        params["severity"] = severity

    if ip_address:
        params["ip_address"] = ip_address

    rows, metadata, error = get_items(
        api_base_url,
        "tenable/findings",
        params,
    )

    if error:
        st.error(error)
    else:
        display_table(
            rows,
            [
                "id",
                "source_finding_id",
                "plugin_id",
                "plugin_name",
                "severity",
                "ip_address",
                "dns_name",
                "host_id",
                "normalized_cvss_base_score",
                "actionable",
                "last_observed",
            ],
        )

# CMDB
with cmdb_tab:
    st.subheader("BMC Helix CMDB Servers")

    rows, metadata, error = get_items(
        api_base_url,
        "cmdb/servers",
        {"limit": record_limit, "offset": 0},
    )

    if error:
        st.error(error)
    else:
        display_table(
            rows,
            [
                "id",
                "source_instance_id",
                "ci_name",
                "dns_host_name",
                "ip_address",
                "os_type",
                "os_version",
                "system_environment",
                "production_status",
                "status",
            ],
        )

# ITSM
with itsm_tab:
    st.subheader("BMC Helix ITSM Changes")

    rows, metadata, error = get_items(
        api_base_url,
        "itsm/changes",
        {"limit": record_limit, "offset": 0},
    )

    if error:
        st.error(error)
    else:
        display_table(
            rows,
            [
                "id",
                "source_change_id",
                "status",
                "impact",
                "urgency",
                "company",
                "support_organization",
                "support_group_name",
                "change_nature",
                "service_ci",
                "environment",
                "scheduled_start_at",
                "scheduled_end_at",
            ],
        )

# Satellite
with satellite_tab:
    st.subheader("Red Hat Satellite Hosts")

    rows, metadata, error = get_items(
        api_base_url,
        "satellite/hosts",
        {"limit": record_limit, "offset": 0},
    )

    if error:
        st.error(error)
    else:
        display_table(
            rows,
            [
                "id",
                "source_host_id",
                "name",
                "ip_address",
                "operating_system",
                "organization_id",
                "location_id",
            ],
        )

    st.subheader("Satellite Job Templates")

    rows, metadata, error = get_items(
        api_base_url,
        "satellite/job-templates",
        {"limit": record_limit, "offset": 0},
    )

    if error:
        st.error(error)
    else:
        display_table(
            rows,
            [
                "id",
                "source_template_id",
                "name",
                "description",
                "template_type",
            ],
        )

st.divider()
st.caption(
    "Read-only dashboard: it does not trigger imports, "
    "modify ITSM records, or execute Satellite jobs."
)