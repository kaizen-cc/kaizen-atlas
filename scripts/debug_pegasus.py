#!/usr/bin/env python3
import sys, datetime
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from atlas.revenue.stripe_pull import fetch_invoices

# Fetch a wider window - check April too
invoices = fetch_invoices(2026, 5)  # fetches Apr+May
for inv in invoices:
    desc = inv.get("description") or ""
    if "pegasus" in desc.lower():
        created = datetime.datetime.fromtimestamp(inv["created"], tz=datetime.timezone.utc)
        print(f"id: {inv.get('id','')[:20]}  created: {created.date()}  status: {inv.get('status')}  amt: ${inv.get('amount_due',0)/100:.0f}")
        print(f"  description: {repr(desc)}")
        lines = (inv.get("lines") or {}).get("data", [])
        for line in lines:
            print(f"  line: ${line.get('amount',0)/100:.0f}  {repr(line.get('description','')[:60])}")
