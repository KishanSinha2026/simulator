"""Generate 20,000 clearly synthetic Tenable-shaped fixture findings."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5

COUNT = 20_000
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "multifindings.json"
PLUGINS = [
    (19506, "Nessus Scan Information", "info", None),
    (10107, "SSH Protocol Version 1 Enabled", "high", 7.5),
    (10002, "Unix Operating System Unsupported", "critical", 9.8),
    (104743, "TLS Version 1.0 Protocol Detection", "medium", 6.5),
    (35716, "SSH Server CBC Mode Ciphers Enabled", "medium", 5.3),
    (57608, "SMB Signing Not Required", "low", 3.7),
]
BASE = datetime(2026, 10, 20, 8, 30, tzinfo=timezone.utc)
FIXTURE_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def main():
    with OUTPUT.open("w", encoding="utf-8") as out:
        out.write("[\n")
        for i in range(1, COUNT + 1):
            plugin_id, name, severity, score = PLUGINS[(i - 1) % len(PLUGINS)]
            # A unique synthetic host per finding keeps host/plugin observations distinct.
            host = i
            host_uuid = str(uuid5(FIXTURE_NAMESPACE, f"tenable-fixture-host-{host}"))
            finding_uuid = str(uuid5(FIXTURE_NAMESPACE, f"tenable-fixture-finding-{i}"))
            first = BASE + timedelta(minutes=i % 10000)
            last = first + timedelta(days=1, minutes=i % 1440)
            row = {
                "id": f"finding-idx-{i:06d}", "source_finding_id": finding_uuid,
                "scan_id": str((i - 1) // 1000 + 1), "plugin_id": plugin_id,
                "plugin_name": name, "family": "Synthetic Security Checks", "ip_address": f"10.{host // 65536}.{(host // 256) % 256}.{host % 256}",
                "dns_name": f"server-{host:05d}.example.invalid", "host_id": host_uuid,
                "severity": severity, "synopsis": f"Synthetic fixture result for {name}.",
                "description": "Synthetic data for API and database development; not a real vulnerability observation.",
                "plugin_output": f"Fixture output record {i}; no real host was scanned.",
                "steps_to_remediate": "Review the vendor guidance and apply an approved change.",
                "cvss_v2_base_score": None, "cvss_v3_base_score": score,
                "cvss_v4_base_score": 6.1 if score is None else None,
                "cve_ids": [f"CVE-2026-{200000 + i}"] if i % 4 == 0 else [],
                "first_discovered": first.isoformat().replace("+00:00", "Z"),
                "last_observed": last.isoformat().replace("+00:00", "Z"),
                "repository": "Synthetic Fixture Repository", "protocol": "tcp", "port": 22 if plugin_id == 10107 else 443,
                "source_payload": {"fixture": True, "severity_id": {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[severity],
                                   "hostname": f"server-{host:05d}", "operating_system": "Linux fixture", "status": "open",
                                   "exploit": "No", "mac_address": f"02:00:{host // 65536 % 256:02x}:{host // 256 % 256:02x}:{host // 16 % 256:02x}:{host % 256:02x}"},
            }
            out.write(json.dumps(row, separators=(",", ":")))
            out.write(",\n" if i < COUNT else "\n")
        out.write("]\n")
    print(f"Created {COUNT} synthetic findings at {OUTPUT}")

if __name__ == "__main__":
    main()

