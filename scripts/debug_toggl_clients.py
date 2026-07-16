#!/usr/bin/env python3
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from atlas.labor.toggl_pull import fetch_projects_with_clients, fetch_user_hours
from atlas.margin.constants import WHITE_LABEL_MAP, AGENCY_TO_CLIENTS
from collections import defaultdict

print("=== Fetching Toggl projects + clients ===")
project_map = fetch_projects_with_clients()

print("=== Fetching May 2026 hours ===")
hour_rows = fetch_user_hours(2026, 5)

# Build client → total seconds
client_secs = defaultdict(int)
for row in hour_rows:
    pid = row["project_id"]
    secs = row["seconds"]
    if not pid or not secs:
        continue
    proj = project_map.get(pid)
    if proj and proj.get("client_name"):
        client_secs[proj["client_name"]] += secs

print("\n=== Hours by agency sub-client ===")
for agency, sub_clients in AGENCY_TO_CLIENTS.items():
    total = sum(client_secs.get(sc, 0) for sc in sub_clients)
    print(f"\n{agency} (total: {total/3600:.1f}h):")
    for sc in sub_clients:
        h = client_secs.get(sc, 0) / 3600
        pct = h / (total / 3600) * 100 if total else 0
        print(f"  {sc}: {h:.1f}h ({pct:.1f}%)")

print("\n=== Toggl client names (all active) ===")
all_toggl = set(v["client_name"] for v in project_map.values() if v.get("client_name"))
wl_keys = set(WHITE_LABEL_MAP.keys())
missing = wl_keys - all_toggl
if missing:
    print("WHITE_LABEL_MAP keys NOT found in Toggl:", missing)
else:
    print("All WHITE_LABEL_MAP keys found in Toggl.")
