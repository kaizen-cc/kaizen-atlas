#!/usr/bin/env python3
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from atlas.revenue.stripe_pull import fetch_invoices
from atlas.revenue.classifier import normalize

invoices = fetch_invoices(2026, 5)

TARGET_AGENCIES = {"RE Creative Agency", "So Shall We", "Lux Marketing Company",
                   "Blue Cherry Group", "ZenChange Marketing", "We Think Big"}

for inv in invoices:
    cname = (inv.get("customer_name") or "").strip()
    if cname not in TARGET_AGENCIES:
        continue
    lines = (inv.get("lines") or {}).get("data", [])
    print(f"\n=== {cname} (invoice {inv.get('id', '')[:12]}) ===")
    for line in lines:
        amt = line.get("amount", 0)
        desc = line.get("description") or ""
        print(f"  ${amt/100:,.2f}  {repr(desc[:80])}")
