#!/usr/bin/env python3
"""Inject Xero MCP P&L data into an existing Atlas snapshot.

The Xero MCP tool does not expose Wages & Salaries or Payroll Tax accounts
(those are Gusto-sourced and filtered by the MCP layer). So we can't trust
the MCP's net_profit field. Instead we compute:

  net_profit = xero_total_income
             - atlas_total_labor   (Toggl hours × rates, covers W-2 + offshore)
             - atlas_total_software (allocation key)
             - xero_overhead        (non-payroll expenses: insurance, auto, etc.)

xero_overhead comes from the MCP expense_accounts list, which correctly
returns everything except Wages/Payroll Tax (already covered by atlas_labor).

Usage:
    python scripts/inject_xero.py --year 2026 --month 6 --data path/to/xero.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from atlas.snapshot import SNAPSHOTS_DIR, _build_xero_incr, save_snapshot

# Expense account names to skip — either covered by atlas_labor or pass-through
SKIP_ACCOUNTS = frozenset([
    "Wages and Salaries",
    "Payroll Tax Expense",
    "Gusto Clearing",
    "Owners Draw",
    "AMEX", "BofA", "Stripe USD", "PayPal",
])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year",  type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--data",  type=str, required=True)
    args = parser.parse_args()

    snap_path = SNAPSHOTS_DIR / f"{args.year}-{args.month:02d}.json"
    if not snap_path.exists():
        print(f"No snapshot found at {snap_path}. Run refresh.py first.")
        sys.exit(1)

    snapshot = json.loads(snap_path.read_text())
    xero = json.loads(Path(args.data).read_text())

    # ── Revenue from Xero (cash basis, includes non-Stripe payments) ──────────
    xero_income = float(xero["current_pnl"]["total_income"])

    # ── Atlas labor and software (computed by Toggl engine during refresh) ────
    atlas_labor    = snapshot["meta"].get("total_labor", 0.0)
    atlas_software = snapshot["meta"].get("total_software", 0.0)

    # ── Non-payroll overhead from Xero MCP expense_accounts ──────────────────
    xero_overhead = 0.0
    for acct in xero.get("expense_accounts", {}).get("all_accounts", []):
        name = acct.get("account_name", "")
        if name in SKIP_ACCOUNTS:
            continue
        try:
            bal = float(acct.get("current_balance", 0))
            if bal > 0:
                xero_overhead += bal
        except (TypeError, ValueError):
            pass

    # ── Net profit ────────────────────────────────────────────────────────────
    net_profit = xero_income - atlas_labor - atlas_software - xero_overhead
    margin_pct = round(net_profit / xero_income * 100, 1) if xero_income else 0.0

    # ── Update snapshot ───────────────────────────────────────────────────────
    stripe_recognized = snapshot["company"].get("stripe_recognized", xero_income)
    snapshot["company"]["xero_total"]  = round(xero_income, 2)
    snapshot["company"]["residual"]    = round(xero_income - stripe_recognized, 2)
    snapshot["company"]["net_profit"]  = round(net_profit, 2)
    snapshot["company"]["margin_pct"]  = margin_pct

    # Update prior if prior snapshot doesn't already have it
    if not snapshot.get("prior", {}).get("net_profit") and xero.get("comparison_pnl"):
        cp = xero["comparison_pnl"]
        snapshot.setdefault("prior", {})["revenue"]    = float(cp["total_income"])
        snapshot["prior"]["net_profit"] = float(cp.get("net_profit", 0))

    # Cost-increase widget
    snapshot["xero_incr"] = _build_xero_incr(xero, None)

    path = save_snapshot(snapshot)
    print(f"Snapshot updated -> {path}")
    print(f"  Xero income:      ${xero_income:>12,.2f}")
    print(f"  Atlas labor:     -${atlas_labor:>12,.2f}")
    print(f"  Atlas software:  -${atlas_software:>12,.2f}")
    print(f"  Xero overhead:   -${xero_overhead:>12,.2f}")
    print(f"  Net profit:       ${net_profit:>12,.2f}  ({margin_pct}%)")
    print(f"  Cost increases:   {len(snapshot['xero_incr'])} items")


if __name__ == "__main__":
    main()
