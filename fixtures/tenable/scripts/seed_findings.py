"""Load the checked-in 20,000-record fixture into PostgreSQL."""
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.db import WriteSessionLocal
from app.models import Finding, Scan

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "multifindings.json"

def parse_dt(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def main():
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    grouped = {}
    for record in records:
        grouped.setdefault(record["scan_id"], []).append(record)
    scan_ids = sorted(grouped, key=int)
    with WriteSessionLocal.begin() as db:
        # Remove the prior generated scan IDs so the fixture has exactly its 20 SC-shaped scans.
        db.execute(delete(Scan).where(Scan.id.like("scan-fixture-%")))
        for scan_id in scan_ids:
            scan_records = grouped[scan_id]
            starts = [parse_dt(r.get("first_discovered")) for r in scan_records]
            finishes = [parse_dt(r.get("last_observed")) for r in scan_records]
            starts = [v for v in starts if v]
            finishes = [v for v in finishes if v]
            scan_values = {
                "id": scan_id, "name": f"Synthetic Fixture Scan {scan_id}",
                "description": "Synthetic scan result for API compatibility; no scan was run.",
                "status": "completed", "result_type": "active",
                "start_time": min(starts) if starts else None,
                "finish_time": max(finishes) if finishes else None,
                "scan_duration": 3600, "repository": "Synthetic Fixture Repository",
                "raw_payload": {"fixture": True, "dataFormat": "IPv4", "resultSource": "internal",
                                "source": "multifindings.json", "synthetic": True},
            }
            db.execute(insert(Scan).values(**scan_values).on_conflict_do_update(
                index_elements=["id"], set_={k: v for k, v in scan_values.items() if k != "id"}))
        values = []
        for r in records:
            p = r.get("source_payload") or {}
            exploit_value = p.get("exploit_available", p.get("exploit"))
            if isinstance(exploit_value, str):
                exploit_value = exploit_value.strip().lower() in {"yes", "true", "1"}
            values.append({
                "id": r["id"], "source_finding_id": r["source_finding_id"], "scan_id": r.get("scan_id"),
                "plugin_id": r.get("plugin_id"), "plugin_name": r.get("plugin_name"),
                "family": r.get("family"), "severity": r.get("severity"), "ip_address": r.get("ip_address"),
                "dns_name": r.get("dns_name"), "host_id": r.get("host_id"), "protocol": r.get("protocol"),
                "port": r.get("port"), "synopsis": r.get("synopsis"), "description": r.get("description"),
                "plugin_output": r.get("plugin_output"), "steps_to_remediate": r.get("steps_to_remediate"),
                "cvss_v2_base_score": r.get("cvss_v2_base_score"), "cvss_v3_base_score": r.get("cvss_v3_base_score"),
                "cvss_v4_base_score": r.get("cvss_v4_base_score"), "cve_ids": r.get("cve_ids") or [],
                "first_discovered": parse_dt(r.get("first_discovered")),
                "last_observed": parse_dt(r.get("last_observed")), "repository": r.get("repository"),
                "status": p.get("status"), "exploit_available": exploit_value, "raw_payload": r,
            })
        for start in range(0, len(values), 1000):
            batch = values[start:start + 1000]
            db.execute(insert(Finding).values(batch).on_conflict_do_update(
                index_elements=["id"],
                set_={key: getattr(insert(Finding).excluded, key) for key in batch[0] if key != "id"},
            ))
    print(f"Loaded {len(records)} fixture findings and {len(scan_ids)} fixture scan records")

if __name__ == "__main__":
    main()

