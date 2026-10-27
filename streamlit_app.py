"""Streamlit frontend for the FastAPI application registered in app/main.py."""

import json
import os
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="VPM360 Dashboard",
    page_icon="🛡️",
    layout="wide",
)


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def get_api_url() -> str:
    """Read the versioned API base URL from secrets or environment."""
    try:
        secret = st.secrets.get("API_BASE_URL", "")
    except Exception:
        secret = ""
    return str(secret or os.getenv("API_BASE_URL", "")).strip().rstrip("/")


def api_url(base_url: str, endpoint: str) -> str:
    """Build a URL for either a relative API path or an OpenAPI absolute path."""
    base = urlsplit(base_url.rstrip("/"))
    route = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    base_path = base.path.rstrip("/")

    if route in {"/openapi.json", "/docs", "/redoc"}:
        deployment_prefix = base_path.removesuffix("/api/v1") if base_path.endswith("/api/v1") else base_path
        full_path = f"{deployment_prefix}{route}"
    elif route == base_path or route.startswith(f"{base_path}/"):
        full_path = route
    elif route.startswith("/api/v1/") or route == "/api/v1":
        # Preserve a deployment prefix such as /vpm while avoiding /api/v1 twice.
        deployment_prefix = base_path.removesuffix("/api/v1") if base_path.endswith("/api/v1") else ""
        full_path = f"{deployment_prefix}{route}"
    else:
        full_path = f"{base_path}{route}"

    return urlunsplit((base.scheme, base.netloc, full_path, "", ""))


def api_request(
    base_url: str,
    method: str,
    endpoint: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
):
    """Call one FastAPI operation and return status, decoded body, and error."""
    if not base_url:
        return None, None, "Enter the FastAPI base URL first."
    try:
        response = httpx.request(
            method=method,
            url=api_url(base_url, endpoint),
            params=params or None,
            json=json_body,
            headers=headers or None,
            timeout=60,
        )
    except httpx.TimeoutException:
        return None, None, f"Request timed out: {method} {endpoint}"
    except httpx.RequestError as exc:
        return None, None, f"Could not connect to the FastAPI backend: {exc}"

    try:
        body = response.json()
    except ValueError:
        body = response.text
    error = None if response.is_success else f"HTTP {response.status_code}"
    return response.status_code, body, error


def get_items(base_url: str, endpoint: str, params: dict[str, Any] | None = None):
    status_code, data, error = api_request(base_url, "GET", endpoint, params=params)
    if error:
        return [], None, f"{error}: {data}"
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)], data, None
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], {"total": len(data)}, None
    return [], None, f"Unexpected list response from {endpoint} (HTTP {status_code})."


def display_table(records: list[dict[str, Any]]) -> None:
    if not records:
        st.info("No records returned.")
        return
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)


def read_openapi_schema(base_url: str):
    """Load the live OpenAPI document and flatten it into selectable operations."""
    status_code, document, error = api_request(base_url, "GET", "/openapi.json")
    if error:
        return None, [], f"{error}: {document}"
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        return None, [], f"Unexpected OpenAPI response (HTTP {status_code})."

    operations = []
    for path, path_item in document["paths"].items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            tags = operation.get("tags") or ["API"]
            summary = operation.get("summary") or operation.get("operationId") or ""
            label = f"{tags[0]} · {method.upper()} {path} · {summary}"
            operations.append({"label": label, "path": path, "method": method.upper(), "definition": operation})
    operations.sort(key=lambda item: (item["label"].split(" · ", 1)[0].lower(), item["path"], item["method"]))
    return document, operations, None


def resolve_schema(schema: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    node: Any = document
    for part in ref.removeprefix("#/").split("/"):
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, dict) else {}


def body_example(schema: dict[str, Any], document: dict[str, Any], depth: int = 0) -> Any:
    """Create an editable starter payload from an OpenAPI JSON schema."""
    if depth > 5:
        return {}
    schema = resolve_schema(schema, document)
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        required = set(schema.get("required", []))
        return {
            key: body_example(value, document, depth + 1)
            for key, value in schema.get("properties", {}).items()
            if key in required
        }
    if kind == "array":
        return []
    if kind == "integer":
        return 0
    if kind == "number":
        return 0.0
    if kind == "boolean":
        return False
    if kind == "string":
        return ""
    return {}


def render_parameter(parameter: dict[str, Any], document: dict[str, Any], key: str):
    """Render an OpenAPI path/query parameter and return its typed value."""
    name = parameter.get("name", "parameter")
    schema = resolve_schema(parameter.get("schema", {}), document)
    label = name + (" *" if parameter.get("required") else "")
    if not parameter.get("required") and schema.get("default") is None:
        if not st.checkbox(f"Set {label}", value=False, key=f"set_{key}"):
            return None
    enum = schema.get("enum")
    if enum:
        return st.selectbox(label, enum, key=key)
    if schema.get("type") == "boolean":
        return st.checkbox(label, value=bool(schema.get("default", False)), key=key)
    if schema.get("type") == "integer":
        return st.number_input(label, value=int(schema.get("default", 0)), step=1, key=key)
    if schema.get("type") == "number":
        return st.number_input(label, value=float(schema.get("default", 0.0)), key=key)
    return st.text_input(label, value=str(schema.get("default", "")), key=key)


def render_api_explorer(base_url: str, document: dict[str, Any], operations: list[dict[str, Any]]) -> None:
    st.subheader("FastAPI operation explorer")
    st.caption("Operations are loaded from the live OpenAPI schema, so this page follows the routes registered in app/main.py.")
    if not operations:
        st.info("The backend returned no documented operations.")
        return

    labels = [operation["label"] for operation in operations]
    selected_label = st.selectbox("Operation", labels)
    operation = next(item for item in operations if item["label"] == selected_label)
    path = operation["path"]
    definition = operation["definition"]
    parameters = list(definition.get("parameters", []))
    path_values: dict[str, Any] = {}
    query_values: dict[str, Any] = {}

    with st.form(f"operation_form_{operation['method']}_{path}"):
        path_parameters = [p for p in parameters if p.get("in") == "path"]
        query_parameters = [p for p in parameters if p.get("in") == "query"]
        if path_parameters:
            st.markdown("**Path parameters**")
            cols = st.columns(min(3, len(path_parameters)))
            for i, parameter in enumerate(path_parameters):
                with cols[i % len(cols)]:
                    path_values[parameter["name"]] = render_parameter(
                        parameter, document, f"path_{path}_{parameter['name']}"
                    )
        if query_parameters:
            st.markdown("**Query parameters**")
            cols = st.columns(min(3, len(query_parameters)))
            for i, parameter in enumerate(query_parameters):
                with cols[i % len(cols)]:
                    query_values[parameter["name"]] = render_parameter(
                        parameter, document, f"query_{path}_{parameter['name']}"
                    )

        request_body = definition.get("requestBody")
        body_text = None
        body_schema = None
        if request_body:
            request_body = resolve_schema(request_body, document)
            content = request_body.get("content", {})
            json_content = content.get("application/json") or next(iter(content.values()), {})
            body_schema = json_content.get("schema", {})
            st.markdown("**Request body**")
            body_text = st.text_area(
                "JSON payload",
                value=json.dumps(body_example(body_schema, document), indent=2),
                height=220,
                key=f"body_{path}_{operation['method']}",
            )
        submitted = st.form_submit_button(f"Send {operation['method']} request")

    with st.expander("Operation details and request schema"):
        st.write(definition.get("description") or definition.get("summary", ""))
        if body_schema:
            st.json(resolve_schema(body_schema, document))

    if not submitted:
        return

    rendered_path = path
    for name, value in path_values.items():
        if value is None or str(value).strip() == "":
            st.error(f"Path parameter '{name}' is required.")
            return
        rendered_path = rendered_path.replace("{" + name + "}", quote(str(value), safe=""))
    query = {
        name: value for name, value in query_values.items()
        if value is not None and value != ""
    }
    payload = None
    if body_text is not None:
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError as exc:
            st.error(f"Request body is not valid JSON: {exc}")
            return

    status_code, response_body, error = api_request(
        base_url,
        operation["method"],
        rendered_path,
        params=query,
        json_body=payload,
    )
    if error:
        st.error(f"{error} for {operation['method']} {rendered_path}")
    else:
        st.success(f"HTTP {status_code}")
    if isinstance(response_body, (dict, list)):
        if isinstance(response_body, dict) and isinstance(response_body.get("items"), list):
            st.caption(f"Returned {len(response_body['items'])} of {response_body.get('total', len(response_body['items']))} records.")
            display_table([row for row in response_body["items"] if isinstance(row, dict)])
        st.json(response_body)
    elif response_body is not None:
        st.code(str(response_body))


def render_list_section(base_url: str, title: str, endpoint: str, limit: int) -> None:
    st.subheader(title)
    rows, metadata, error = get_items(base_url, endpoint, {"limit": limit, "offset": 0})
    if error:
        st.error(error)
    else:
        if metadata:
            st.caption(f"Showing {len(rows)} of {metadata.get('total', len(rows))} records.")
        display_table(rows)


st.title("VPM360 Integration Dashboard")
st.caption("Streamlit frontend for the FastAPI service. Connect it to the Uvicorn URL that Streamlit can reach.")

with st.sidebar:
    st.header("Backend Configuration")
    api_base_url = st.text_input(
        "FastAPI base URL",
        value=get_api_url(),
        placeholder="https://your-api.example.com/api/v1",
        help="For Streamlit Cloud, set API_BASE_URL in the app's Secrets to your publicly reachable FastAPI URL, ending in /api/v1.",
    ).strip().rstrip("/")
    if st.button("Refresh dashboard"):
        st.rerun()

if not api_base_url:
    st.info("Set API_BASE_URL in Streamlit Cloud Secrets to the public FastAPI URL ending in /api/v1, or enter it in the sidebar.")
    st.stop()

health_status, health, health_error = api_request(api_base_url, "GET", "health")
if health_error:
    if "Could not connect" in health_error:
        st.error(
            "FastAPI health check failed: Streamlit cannot reach this backend. "
            "On Streamlit Cloud, localhost points to the Streamlit container. "
            "Deploy FastAPI/Uvicorn at a reachable URL and set API_BASE_URL in Streamlit Secrets. "
            f"Connection detail: {health_error}"
        )
    else:
        st.error(f"FastAPI health check failed: {health_error}")
else:
    st.success(f"FastAPI connected (HTTP {health_status}).")

openapi_document, operations, openapi_error = read_openapi_schema(api_base_url)
if openapi_error:
    st.warning(f"Could not load the backend route catalog: {openapi_error}")

tab_names = ["Overview", "Tenable", "Squad1", "CMDB", "ITSM", "Satellite", "SCCM", "All API Routes"]
tabs = st.tabs(tab_names)

with tabs[0]:
    st.subheader("Integration overview")
    resources = [
        ("Tenable findings", "tenable/findings"),
        ("Squad1 vulnerabilities", "squad1/vulnerabilities"),
        ("CMDB servers", "cmdb/servers"),
        ("ITSM changes", "itsm/changes"),
        ("Satellite hosts", "satellite/hosts"),
        ("SCCM devices", "sccm/devices"),
    ]
    for start in range(0, len(resources), 3):
        cols = st.columns(3)
        for col, (label, endpoint) in zip(cols, resources[start:start + 3]):
            _, metadata, error = get_items(api_base_url, endpoint, {"limit": 100, "offset": 0})
            if error:
                col.metric(label, "Unavailable")
                col.caption(error)
            else:
                col.metric(label, metadata.get("total", "Connected") if metadata else "Connected")
    st.markdown("**Health response**")
    if health_error:
        st.error(health_error)
    else:
        st.json(health)
    if openapi_document:
        st.caption(f"{len(operations)} documented API operations are available in the All API Routes tab.")

with tabs[1]:
    render_list_section(api_base_url, "Tenable findings", "tenable/findings", 100)
    render_list_section(api_base_url, "Tenable scans", "tenable/scans", 100)

with tabs[2]:
    render_list_section(api_base_url, "Squad1 vulnerabilities", "squad1/vulnerabilities", 100)
    render_list_section(api_base_url, "Squad1 exceptions", "squad1/exceptions", 100)

with tabs[3]:
    render_list_section(api_base_url, "BMC Helix CMDB servers", "cmdb/servers", 100)
    st.markdown("Correlate a finding IP with the CMDB server CI using the route in **All API Routes**.")

with tabs[4]:
    render_list_section(api_base_url, "BMC Helix ITSM changes", "itsm/changes", 100)

with tabs[5]:
    render_list_section(api_base_url, "Red Hat Satellite hosts", "satellite/hosts", 100)
    render_list_section(api_base_url, "Satellite job templates", "satellite/job-templates", 100)

with tabs[6]:
    render_list_section(api_base_url, "SCCM devices", "sccm/devices", 100)
    render_list_section(api_base_url, "SCCM collections", "sccm/collections", 100)
    render_list_section(api_base_url, "SCCM deployments", "sccm/deployments", 100)
    render_list_section(api_base_url, "SCCM deployment runs", "sccm/jobs", 100)

with tabs[7]:
    if openapi_error:
        st.error("The route explorer needs a reachable FastAPI /openapi.json endpoint.")
    elif openapi_document:
        render_api_explorer(api_base_url, openapi_document, operations)

st.divider()
st.caption("Use All API Routes to call every operation published by the connected FastAPI OpenAPI schema, including detail, import, update, worklog, and execution operations.")
