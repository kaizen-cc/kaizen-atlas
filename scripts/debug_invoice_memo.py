#!/usr/bin/env python3
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from atlas.revenue.stripe_pull import fetch_invoices

TARGET_AGENCIES = {"RE Creative Agency", "So Shall We", "Lux Marketing Company",
                   "Blue Cherry Group", "ZenChange Marketing", "We Think Big"}

invoices = fetch_invoices(2026, 5)

for inv in invoices:
    cname = (inv.get("customer_name") or "").strip()
    if cname not in TARGET_AGENCIES:
        continue
    print(f"\n--- {cname} ({inv.get('id','')[:16]}) ---")
    print(f"  description:    {repr(inv.get('description'))}")
    print(f"  footer:         {repr(inv.get('footer'))}")
    print(f"  memo:           {repr(inv.get('memo'))}")
    print(f"  metadata:       {inv.get('metadata')}")
    print(f"  statement_desc: {repr(inv.get('statement_descriptor'))}")
    lines = (inv.get("lines") or {}).get("data", [])
    for line in lines:
        amt = line.get("amount", 0)
        desc = line.get("description") or ""
        meta = line.get("metadata")
        print(f"  line ${amt/100:.0f}: {repr(desc[:60])}  meta={meta}")
