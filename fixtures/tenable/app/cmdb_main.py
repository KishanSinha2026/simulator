"""Read-only BMC Helix CMDB v1.0-compatible fixture API backed by PostgreSQL."""
import base64
import hashlib
import hmac
import json
import re
import time
from typing import Any
from urllib.parse import parse_qs

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from fastapi.security import APIKeyHeader
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.cmdb_db import CMDBSession
from app.cmdb_models import ComputerSystem, IPEndpoint
from app.config import settings

router = APIRouter(tags=["CMDB"])
cmdb_jwt_header = APIKeyHeader(
    name="Authorization",
    scheme_name="CMDBARJWT",
    description="Enter: AR-JWT <token returned by POST /api/jwt/login>",
    auto_error=False,
)

OS_FIELDS = [
    "CMDB Instance ID", "CI Name*", "DNS Host Name", "IP Address", "Location", "Application Name",
    "IBL_SPOC/Assest Owner", "IT Application Owner", "System Environment", "Prod/Non Prod", "is Virtual",
    "Internet Facing", "Virtual System Type", "IBL_Asset_Type", "Product Name+", "IBL_Server_Type",
    "IBL_Operating_System", "OS Type", "IBL_RiskClassification__", "Target Date", "Last Patched Date", "Aging",
]
MIDDLEWARE_FIELDS = [
    "CMDB Instance ID", "CMDB CI", "Username", "Hostname", "IP Address", "Location", "Application Name",
    "IBL_SPOC/Assest Owner", "IT Application Owner", "Technology", "Environment", "Prod/Non Prod", "CORE",
    "Os Type", "Installed Version", "Recommended update version", "Latest Patch Release Date",
    "End of suppport date", "Target Date",
]
DATABASE_FIELDS = [
    "CMDB Instance ID", "CMDB CI", "IP", "Location", "Assest Owner", "Hostname", "Technology",
    "Environment", "Prod/Non Prod", "IBL_DB_Version", "IBL_RiskClassification__", "Last Patched date", "Ageing", "Target Date",
]
CMDB_ATTRIBUTE_FIELDS = list(dict.fromkeys(OS_FIELDS + MIDDLEWARE_FIELDS + DATABASE_FIELDS))

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def issue_token(username: str) -> str:
    now = int(time.time())
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = b64url(json.dumps({"sub": username, "iss": settings.cmdb_base_url, "iat": now,
                                "nbf": now - 120, "exp": now + 3600, "_cacheId": 1}, separators=(",", ":")).encode())
    message = f"{header}.{claims}".encode()
    signature = hmac.new(settings.cmdb_jwt_secret.encode(), message, hashlib.sha256).digest()
    return f"{header}.{claims}.{b64url(signature)}"

def require_cmdb_jwt(authorization: str | None = Depends(cmdb_jwt_header)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("AR-JWT "):
        raise HTTPException(status_code=401, detail="Authorization must use the AR-JWT scheme")
    token = authorization[7:].strip()
    if settings.data == "API":
        return {"_upstream_token": token}
    try:
        header, claims, signature = token.split(".")
        expected = b64url(hmac.new(settings.cmdb_jwt_secret.encode(), f"{header}.{claims}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("expired")
        return payload
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired AR-JWT token") from exc

def forward_cmdb(path: str, *, token: str | None = None, params: dict | None = None,
                 form: dict | None = None) -> Response:
    if not settings.cmdb_source_url:
        raise HTTPException(status_code=503, detail="CMDB_SOURCE_URL is required when DATA=API")
    headers = {"Authorization": f"AR-JWT {token}"} if token else {}
    try:
        upstream = httpx.request("GET" if form is None else "POST",
                                 settings.cmdb_source_url.rstrip("/") + path,
                                 headers=headers, params=params, data=form, timeout=30.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the configured CMDB API") from exc
    status = upstream.status_code if upstream.status_code < 500 else 502
    return Response(content=upstream.content, status_code=status,
                    media_type=upstream.headers.get("content-type", "application/json"))

def upstream_token(auth: dict[str, Any]) -> str | None:
    return auth.get("_upstream_token")

def ensure_cmdb_db_configured() -> None:
    if not settings.cmdb_database_url or "change-me" in settings.cmdb_database_url:
        raise HTTPException(status_code=503, detail="Set DATABASE_URL or CMDB_DATABASE_URL in the server .env when DATA=DB")

def link(path: str) -> dict[str, list[dict[str, str]]]:
    return {"self": [{"href": settings.cmdb_base_url.rstrip("/") + path}]}

def instance_object(ci: ComputerSystem) -> dict[str, Any]:
    return {"instance_id": ci.instance_id,
            "class_name_key": {"name": "BMC_ComputerSystem", "namespace": "BMC.CORE"},
            "dataset_id": ci.dataset_id, "attributes": ci.attributes,
            "_links": link(f"/api/cmdb/v1.0/instances/{ci.dataset_id}/BMC.CORE/BMC_ComputerSystem/{ci.instance_id}")}

def _get_db():
    db = CMDBSession()
    try:
        yield db
    finally:
        db.close()

@router.post("/api/jwt/login", response_class=PlainTextResponse)
async def cmdb_login(request: Request):
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            credentials = json.loads(body or b"{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "Invalid JSON login body") from exc
    else:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        credentials = {key: values[0] for key, values in parsed.items()}
    username = str(credentials.get("username", ""))
    password = str(credentials.get("password", ""))
    user_ok = hmac.compare_digest(username, settings.cmdb_username)
    pass_ok = hmac.compare_digest(password, settings.cmdb_password)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Invalid CMDB username or password")
    if settings.data == "API":
        response = forward_cmdb("/api/jwt/login", form={"username": username, "password": password})
        return Response(content=response.body, status_code=response.status_code,
                        media_type=response.media_type or "text/plain")
    return issue_token(username)

@router.get("/api/cmdb/v1.0/instances/{datasetId}/BMC.CORE/BMC_IPEndpoint")
def find_ip_endpoints(
    datasetId: str,
    auth: dict = Depends(require_cmdb_jwt),
    qualification: str | None = None,
    limit: int = Query(default=500, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    attributes: str | None = None,
    db: Session = Depends(_get_db),
):
    if settings.data == "API":
        params = {k: v for k, v in {"qualification": qualification, "attributes": attributes,
                                     "limit": limit, "offset": offset}.items() if v is not None}
        return forward_cmdb(f"/api/cmdb/v1.0/instances/{datasetId}/BMC.CORE/BMC_IPEndpoint",
                            token=upstream_token(auth), params=params)
    ensure_cmdb_db_configured()
    statement = select(IPEndpoint).where(IPEndpoint.dataset_id == datasetId)
    if qualification:
        match = re.search(r"(?i)\bAddress\b\s*(?:=|LIKE)\s*[\"']?([0-9a-fA-F:.]+)", qualification)
        if match:
            address = match.group(1).rstrip("\"'")
            statement = statement.where(IPEndpoint.address == address)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(statement.order_by(IPEndpoint.address).offset(offset).limit(limit)).all()
    requested = {part.strip() for part in attributes.split(",")} if attributes else None
    instances = []
    for row in rows:
        attrs = dict(row.attributes)
        if requested:
            attrs = {key: value for key, value in attrs.items() if key in requested}
        instances.append({"instance_id": row.instance_id,
                          "class_name_key": {"name": "BMC_IPEndpoint", "namespace": "BMC.CORE"},
                          "dataset_id": row.dataset_id, "attributes": attrs,
                          "_links": link(f"/api/cmdb/v1.0/instances/{datasetId}/BMC.CORE/BMC_IPEndpoint/{row.instance_id}")})
    return {"instances": instances, "num_matches": total}

@router.get("/api/cmdb/v1.0/graphwalk")
def graphwalk(
    graph_walk_query: str,
    auth: dict = Depends(require_cmdb_jwt),
    db: Session = Depends(_get_db),
):
    if settings.data == "API":
        return forward_cmdb("/api/cmdb/v1.0/graphwalk", token=upstream_token(auth),
                            params={"graph_walk_query": graph_walk_query})
    ensure_cmdb_db_configured()
    try:
        query = json.loads(graph_walk_query)
        start = query["start_node"]["instance_id"]
        dataset_id = query.get("dataset_id", settings.cmdb_dataset_id)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HTTPException(400, "graph_walk_query must contain dataset_id and start_node.instance_id") from exc
    endpoint = db.get(IPEndpoint, start)
    if endpoint and endpoint.dataset_id == dataset_id:
        ci = db.get(ComputerSystem, endpoint.computer_system_instance_id)
        direction = "IP endpoint to server CI"
    else:
        ci = db.get(ComputerSystem, start)
        endpoint = db.scalar(select(IPEndpoint).where(IPEndpoint.computer_system_instance_id == start,
                                                      IPEndpoint.dataset_id == dataset_id)) if ci else None
        direction = "server CI to IP endpoint"
    if ci is None or ci.dataset_id != dataset_id:
        return {"relationship_cis": [], "class_cis": []}
    system = instance_object(ci)
    if direction.startswith("IP"):
        class_cis = [system]
        relation = {"instance_id": f"REL-{endpoint.instance_id}",
                    "class_name_key": {"name": "BMC_HostedAccessPoint", "namespace": "BMC.CORE"},
                    "attributes": {"Name": f"Hosted address {endpoint.address}",
                                   "Source.InstanceId": ci.instance_id,
                                   "Destination.InstanceId": endpoint.instance_id}}
    else:
        class_cis = [{"instance_id": endpoint.instance_id,
                      "class_name_key": {"name": "BMC_IPEndpoint", "namespace": "BMC.CORE"},
                      "dataset_id": endpoint.dataset_id, "attributes": endpoint.attributes,
                      "_links": link(f"/api/cmdb/v1.0/instances/{dataset_id}/BMC.CORE/BMC_IPEndpoint/{endpoint.instance_id}")}]
        relation = {"instance_id": f"REL-{endpoint.instance_id}",
                    "class_name_key": {"name": "BMC_HostedAccessPoint", "namespace": "BMC.CORE"},
                    "attributes": {"Name": f"Hosted address {endpoint.address}",
                                   "Source.InstanceId": ci.instance_id,
                                   "Destination.InstanceId": endpoint.instance_id}}
    return {"relationship_cis": [relation], "class_cis": class_cis}

@router.get("/api/cmdb/v1.0/instances/{datasetId}/BMC.CORE/BMC_ComputerSystem/{instanceId}")
def get_computer_system(datasetId: str, instanceId: str,
                        auth: dict = Depends(require_cmdb_jwt), db: Session = Depends(_get_db)):
    if settings.data == "API":
        return forward_cmdb(f"/api/cmdb/v1.0/instances/{datasetId}/BMC.CORE/BMC_ComputerSystem/{instanceId}",
                            token=upstream_token(auth))
    ensure_cmdb_db_configured()
    ci = db.get(ComputerSystem, instanceId)
    if ci is None or ci.dataset_id != datasetId:
        raise HTTPException(status_code=404, detail="ComputerSystem CI not found")
    return instance_object(ci)

@router.get("/api/cmdb/v1.0/attributes/BMC.CORE/BMC_ComputerSystem")
def get_computer_system_attributes(
    auth: dict = Depends(require_cmdb_jwt),
):
    if settings.data == "API":
        return forward_cmdb("/api/cmdb/v1.0/attributes/BMC.CORE/BMC_ComputerSystem",
                            token=upstream_token(auth))
    ensure_cmdb_db_configured()
    names = ["InstanceId", "DatasetId", "Name", "ClassId", "MarkAsDeleted", *CMDB_ATTRIBUTE_FIELDS]
    result = []
    for index, name in enumerate(dict.fromkeys(names), start=1):
        data_type = "INTEGER" if name in {"Aging", "Ageing", "CORE"} else ("DATE" if "Date" in name or "date" in name else "CHAR")
        result.append({"name": name, "type": "CORE" if name in {"InstanceId", "DatasetId", "Name", "ClassId", "MarkAsDeleted"} else "REGULAR",
                       "datatype": data_type, "characteristics": {}, "limit": {}, "attribute_id": str(500000 + index),
                       "field_id": 500000 + index, "entry_mode": "OPTIONAL"})
    return result


# Preserve standalone use while allowing the main Tenable app to include these
# routes in its own OpenAPI page and on the same host/port.
app = FastAPI(title="VPM360 BMC CMDB-compatible API", version="1.0.0", docs_url="/docs", redoc_url=None)
app.include_router(router)

