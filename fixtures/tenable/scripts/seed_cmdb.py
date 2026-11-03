"""Seed synthetic BMC CMDB-shaped CIs and IP endpoints for the Tenable fixture IPs."""
import json
from pathlib import Path
from uuid import UUID, uuid5

from sqlalchemy.dialects.postgresql import insert

from app.cmdb_db import CMDBSession
from app.cmdb_models import ComputerSystem, IPEndpoint
from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
TENABLE_FIXTURE = ROOT / "multifindings.json"
NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def ci_attributes(row, i, instance_id, inventory_type):
    ip = row["ip_address"]
    host = row["dns_name"].split(".")[0]
    production = i % 3 == 0
    environment = "Production" if production else ("UAT" if i % 3 == 1 else "Development")
    owner = f"Synthetic Owner {i:05d}"
    attrs = {
        "InstanceId": instance_id, "DatasetId": settings.cmdb_dataset_id, "ClassId": "BMC_ComputerSystem",
        "MarkAsDeleted": False, "isVirtual": "Yes", "Virtual": "Yes",
        "CMDB Instance ID": instance_id, "CI Name*": row["dns_name"], "DNS Host Name": host,
        "IP Address": ip, "Location": ["Mumbai", "Pune", "Bengaluru"][i % 3],
        "Application Name": f"Synthetic Application {i % 250 + 1:03d}",
        "IBL_SPOC/Assest Owner": owner, "IT Application Owner": f"Application Owner {i % 500 + 1:03d}",
        "System Environment": environment, "Prod/Non Prod": "Prod" if production else "Non Prod",
        "is Virtual": "Yes", "Internet Facing": "No", "Virtual System Type": "VMware",
        "IBL_Asset_Type": "Virtual Server", "Product Name+": "VMware Virtual Platform",
        "IBL_Server_Type": "App", "IBL_Operating_System": row["source_payload"].get("operating_system", "Linux"),
        "OS Type": "Windows" if "Windows" in row["source_payload"].get("operating_system", "") else "Linux",
        "IBL_RiskClassification__": ["Low", "Medium", "High"][i % 3],
        "Target Date": "2026-12-15", "Last Patched Date": "2026-09-15", "Aging": str(i % 365),
        "VPM360 Inventory Type": inventory_type,
    }
    if inventory_type == "Middleware":
        attrs.update({
            "CMDB CI": row["dns_name"], "Username": f"svc_app_{i:05d}", "Hostname": host,
            "Technology": ["JBOSS", "WebSphere", "IIS"][i % 3], "Environment": environment,
            "CORE": str(i % 8 + 1), "Os Type": attrs["OS Type"], "Installed Version": f"8.1.{i % 10}.0",
            "Recommended update version": f"8.1.{i % 10}.1", "Latest Patch Release Date": "2026-07-07",
            "End of suppport date": "2031-02-05",
        })
    elif inventory_type == "Database":
        attrs.update({
            "CMDB CI": row["dns_name"], "IP": ip, "Assest Owner": owner,
            "Hostname": host, "Technology": ["IBM DB2", "Oracle", "SQL Server"][i % 3],
            "Environment": environment, "IBL_DB_Version": ["IBM DB2 11.5 Standard Edition", "Oracle 19c", "SQL Server 2022"][i % 3],
            "Last Patched date": "2026-09-15",
        })
    return attrs

def main():
    records = json.loads(TENABLE_FIXTURE.read_text(encoding="utf-8"))
    ci_values, endpoint_values = [], []
    for i, row in enumerate(records, start=1):
        ci_id = "OI-" + uuid5(NAMESPACE, f"cmdb-ci-{i}").hex.upper()
        ip_id = "OI-" + uuid5(NAMESPACE, f"cmdb-ip-{i}").hex.upper()
        inventory_type = ("Operating System", "Middleware", "Database")[(i - 1) % 3]
        attrs = ci_attributes(row, i, ci_id, inventory_type)
        ci_values.append({"instance_id": ci_id, "dataset_id": settings.cmdb_dataset_id,
                          "inventory_type": inventory_type, "attributes": attrs})
        ip_attrs = {"InstanceId": ip_id, "DatasetId": settings.cmdb_dataset_id, "ClassId": "BMC_IPEndpoint",
                    "Address": row["ip_address"], "Name": row["ip_address"], "NameFormat": "IP",
                    "SystemName": row["dns_name"]}
        endpoint_values.append({"instance_id": ip_id, "dataset_id": settings.cmdb_dataset_id,
                                "address": row["ip_address"], "computer_system_instance_id": ci_id,
                                "attributes": ip_attrs})
    with CMDBSession.begin() as db:
        for model, values, conflict in ((ComputerSystem, ci_values, "instance_id"), (IPEndpoint, endpoint_values, "instance_id")):
            for start in range(0, len(values), 1000):
                batch = values[start:start + 1000]
                db.execute(insert(model).values(batch).on_conflict_do_update(
                    index_elements=[conflict], set_={k: getattr(insert(model).excluded, k) for k in batch[0] if k != conflict}))
    print(f"Loaded {len(ci_values)} unique CMDB server CIs and {len(endpoint_values)} IP endpoints into {settings.cmdb_dataset_id}")

if __name__ == "__main__":
    main()

