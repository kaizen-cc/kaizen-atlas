#!/usr/bin/env python3
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from atlas.revenue.stripe_pull import fetch_invoices
from atlas.revenue.classifier import normalize, map_to_team
from collections import Counter, defaultdict

invoices = fetch_invoices(2026, 5)
team_totals = Counter()
other_descs = defaultdict(float)

for inv in invoices:
    lines = (inv.get("lines") or {}).get("data", [])
    for line in lines:
        amt = line.get("amount", 0)
        if amt <= 0:
            continue
        desc = line.get("description") or ""
        norm = normalize(desc)
        team = map_to_team(desc)
        team_totals[team] += amt / 100
        if team == "Other":
            other_descs[norm] += amt / 100

print("=== Team totals ===")
for t, v in sorted(team_totals.items(), key=lambda x: -x[1]):
    print(f"  {t}: ${v:,.0f}")

print()
print("=== Unmatched descriptions (Other) ===")
for d, v in sorted(other_descs.items(), key=lambda x: -x[1])[:25]:
    print(f"  ${v:,.0f}  {repr(d)}")
