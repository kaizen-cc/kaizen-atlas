#!/usr/bin/env python3
"""Daily refresh job.

Computes the full margin model for a given month and writes a dated snapshot
to data/snapshots/YYYY-MM.json.  Run from the project root:

    python scripts/refresh.py                  # current month
    python scripts/refresh.py --year 2026 --month 5   # specific month
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from atlas.margin.engine import compute_margin
from atlas.revenue.engine import compute_revenue
from atlas.software.engine import compute_software
from atlas.snapshot import build_snapshot, load_snapshot, save_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Kaizen Atlas daily refresh")
    now = datetime.now(timezone.utc)
    parser.add_argument("--year",  type=int, default=now.year)
    parser.add_argument("--month", type=int, default=now.month)
    args = parser.parse_args()

    year, month = args.year, args.month
    print(f"[atlas refresh] Computing {year}-{month:02d}...")

    # ── Run engines ──────────────────────────────────────────────────────────
    print("  revenue engine...")
    revenue = compute_revenue(year, month)

    print("  margin engine (labor + software)...")
    margin = compute_margin(year, month)

    software = compute_software()

    # ── Prior month snapshot for MoM and history ─────────────────────────────
    prior_month = month - 1 if month > 1 else 12
    prior_year  = year if month > 1 else year - 1
    prior_snapshot = load_snapshot(prior_year, prior_month)
    if prior_snapshot:
        print(f"  loaded prior snapshot ({prior_year}-{prior_month:02d})")
    else:
        print(f"  no prior snapshot found — MoM deltas will be empty")

    # ── Xero P&L — source of truth for revenue, costs, and net profit ────────
    xero_pnl = None
    xero_pnl_prior = None
    xero_actuals = None
    try:
        from atlas.software.xero_pull import _is_available, _refresh_access_token
        import urllib.request, urllib.parse, urllib.error, json

        if _is_available():
            from atlas.config import require
            import calendar
            token = _refresh_access_token()
            tenant_id = require("XERO_TENANT_ID")

            def _xero_pnl(yr, mo):
                last_day = calendar.monthrange(yr, mo)[1]
                params = urllib.parse.urlencode({
                    "fromDate": f"{yr}-{mo:02d}-01",
                    "toDate":   f"{yr}-{mo:02d}-{last_day:02d}",
                })
                url = f"https://api.xero.com/api.xro/2.0/Reports/ProfitAndLoss?{params}"
                req = urllib.request.Request(url, headers={
                    "Authorization": f"Bearer {token}",
                    "Xero-tenant-id": tenant_id,
                    "Accept": "application/json",
                })
                with urllib.request.urlopen(req) as r:
                    return json.loads(r.read())

            print("  fetching Xero P&L (current month)...")
            xero_pnl = _xero_pnl(year, month)
            xero_actuals = _parse_xero_pnl(xero_pnl)
            print(f"  Xero P&L fetched — income={xero_actuals.get('total_income')}, net={xero_actuals.get('net_profit')}")

            print("  fetching Xero P&L (prior month for cost comparison)...")
            try:
                xero_pnl_prior = _xero_pnl(prior_year, prior_month)
                print("  Xero prior P&L fetched")
            except Exception as exc2:
                print(f"  Xero prior P&L failed ({exc2}) — cost increases will be skipped")
        else:
            print("  Xero credentials not set — skipping Xero pull")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        print(f"  Xero fetch failed ({exc}) — body: {body[:500]}")
    except Exception as exc:
        print(f"  Xero fetch failed ({exc}) — continuing without")

    # ── Build and save snapshot ───────────────────────────────────────────────
    generated_at = datetime.now(timezone.utc).isoformat()
    snapshot = build_snapshot(
        year=year,
        month=month,
        margin_result=margin,
        revenue_result=revenue,
        software_result=software,
        prior_snapshot=prior_snapshot,
        xero_pnl_current=xero_pnl,
        xero_pnl_prior=xero_pnl_prior,
        xero_actuals=xero_actuals,
        generated_at=generated_at,
    )

    path = save_snapshot(snapshot)
    print(f"  snapshot saved -> {path}")

    # ── Push to Supabase (kaizen-cc) ─────────────────────────────────────────
    _push_to_supabase(snapshot, year, month, generated_at)

    # Summary
    co = snapshot["company"]
    print(f"\n  Revenue  ${co['revenue']:>10,.0f}")
    print(f"  Labor    ${snapshot['meta'].get('total_labor', '—')}")
    print(f"  Net      ${co['net_profit']:>10,.0f}  ({co['margin_pct']}%)")
    if snapshot["low_tracking_flags"]:
        print(f"\n  Low-tracking flags: {', '.join(snapshot['low_tracking_flags'])}")


def _push_to_supabase(snapshot: dict, year: int, month: int, generated_at: str) -> None:
    """Push the built snapshot to the kaizen-cc Supabase atlas_snapshots table."""
    import json, urllib.request, urllib.error

    # Load Supabase credentials from .env
    try:
        from atlas.config import get
        supabase_url    = get("SUPABASE_URL")
        supabase_key    = get("SUPABASE_SERVICE_KEY")  # service role key
        supabase_agency = get("SUPABASE_AGENCY_ID")
    except Exception:
        supabase_url = supabase_key = supabase_agency = None

    if not supabase_url or not supabase_key or not supabase_agency:
        print("  Supabase credentials not set — skipping cloud push")
        print("  Set SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_AGENCY_ID in .env to enable")
        return

    payload = json.dumps({
        "agency_id":    supabase_agency,
        "year":         year,
        "month":        month,
        "snapshot":     snapshot,
        "generated_at": generated_at,
    }).encode()

    url = f"{supabase_url}/rest/v1/atlas_snapshots?on_conflict=agency_id,year,month"
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "apikey":         supabase_key,
            "Authorization":  f"Bearer {supabase_key}",
            "Content-Type":   "application/json",
            "Prefer":         "resolution=merge-duplicates",  # upsert
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            print(f"  pushed to Supabase (status {r.status})")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  Supabase push failed ({e.code}): {body[:200]}")
    except Exception as exc:
        print(f"  Supabase push failed: {exc}")


def _parse_xero_pnl(raw: dict) -> dict:
    """Extract total_income and net_profit from a raw Xero ProfitAndLoss response."""
    result = {"total_income": None, "total_costs": None, "net_profit": None}
    try:
        rows = raw["Reports"][0]["Rows"]
    except (KeyError, IndexError):
        return result

    def _val(cells, idx=1):
        try:
            v = str(cells[idx].get("Value", "") or "").replace(",", "").strip()
            return float(v) if v else None
        except (ValueError, IndexError):
            return None

    def _scan_all_rows(section_rows):
        """Yield (label, value) for every row with cells, recursively."""
        for row in section_rows:
            cells = row.get("Cells", [])
            label = cells[0].get("Value", "") if cells else ""
            if label:
                yield label, _val(cells)
            for sub in row.get("Rows", []):
                yield from _scan_all_rows([sub])

    for label, val in _scan_all_rows(rows):
        if val is None:
            continue
        lc = label.lower()
        if "total revenue" in lc or "total income" in lc:
            result["total_income"] = val
        elif lc in ("net income", "net loss", "net profit"):
            result["net_profit"] = val if "loss" not in lc else -val

    if result["total_income"] and result["net_profit"] is not None:
        result["total_costs"] = round(result["total_income"] - result["net_profit"], 2)

    return result


if __name__ == "__main__":
    main()
