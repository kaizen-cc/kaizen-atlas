#!/usr/bin/env python3
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from atlas.revenue.stripe_pull import fetch_invoices

invoices = fetch_invoices(2026, 5)
for inv in invoices[:5]:
    lines = (inv.get("lines") or {}).get("data", [])
    for line in lines[:2]:
        desc = line.get("description") or ""
        if desc:
            print(repr(desc[:30]))
            print([hex(ord(c)) for c in desc[:10]])
            break
    break
