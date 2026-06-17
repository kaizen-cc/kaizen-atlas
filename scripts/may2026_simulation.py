#!/usr/bin/env python3
"""
May 2026 Revenue Simulation
Processes two Stripe API pages, merges invoices, runs simulation against fixtures.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── File paths ──────────────────────────────────────────────────────────────
PAGE1 = Path(r"C:\Users\lozan\.claude\projects\C--Users-lozan-Projects-kaizen-cc\c34c7a91-cbb0-49e3-aab5-2d8e82daf063\tool-results\mcp-bd48e178-6046-4c32-a1a3-a4e872c786ca-stripe_api_read-1781718225726.txt")
PAGE2 = Path(r"C:\Users\lozan\.claude\projects\C--Users-lozan-Projects-kaizen-cc\c34c7a91-cbb0-49e3-aab5-2d8e82daf063\tool-results\mcp-bd48e178-6046-4c32-a1a3-a4e872c786ca-stripe_api_read-1781718672767.txt")
FIXTURES = Path(r"C:\Users\lozan\Projects\kaizen-atlas\tests\fixtures\kaizen_atlas_fixtures.json")

# ── Normalization patterns ───────────────────────────────────────────────────
RE_LEAD  = re.compile(r'^\d+\s*[xX×•·]\s*')
RE_TRAIL = re.compile(r'\s*\(at \$[\d,]+\.?\d*\s*/\s*\w+\)\s*$')

def normalize(desc: str) -> str:
    if not desc:
        return ""
    s = RE_LEAD.sub('', desc)
    s = RE_TRAIL.sub('', s)
    return s.strip()

# ── Service → Team mapping ───────────────────────────────────────────────────
SERVICE_TO_TEAM = {
    "Meta Advertising":         "Meta",
    "TikTok Advertising":       "Meta",
    "Google Advertising":       "Google",
    "Email Marketing":          "Email",
    "SMS Marketing":            "Email",
    "Organic Social":           "Social",
    "Social Media Management":  "Social",
    "Content Creation":         "Social",
    "Website Development":      "Web",
    "Creative Package":         "Creative",
    "SEO":                      "SEO",
    "CRM":                      "GHL",
    "CRM Maintenance":          "GHL",
}

def map_team(desc_norm: str) -> str:
    return SERVICE_TO_TEAM.get(desc_norm, "Other")

# ── Off-Stripe rescue clients ────────────────────────────────────────────────
OFF_STRIPE_RESCUE = {"Tejas Brewery", "Giant Texas", "Tejas Beer", "Oceanbox"}

# ── Helpers ──────────────────────────────────────────────────────────────────
def ts_to_dt(ts) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)

def in_may_2026(ts) -> bool:
    dt = ts_to_dt(ts)
    return dt.year == 2026 and dt.month == 5

# ── Load + parse Stripe page ─────────────────────────────────────────────────
def load_stripe_page(path: Path):
    """
    The Stripe API tool result may be raw JSON or wrapped in text.
    Try to extract JSON from the file.
    """
    text = path.read_text(encoding='utf-8')
    # Find the outermost JSON object
    start = text.find('{')
    if start == -1:
        # maybe it's a JSON array
        start = text.find('[')
    if start == -1:
        raise ValueError(f"No JSON found in {path}")
    # Find matching close — use json.JSONDecoder raw_decode
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text, start)
    return obj

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("MAY 2026 REVENUE SIMULATION")
    print("=" * 70)

    # 1. Load pages
    print("\n[1] Loading Stripe pages...")
    page1 = load_stripe_page(PAGE1)
    page2 = load_stripe_page(PAGE2)

    # Detect structure: could be {"data": [...], "has_more": ...} or {"invoices": [...]}
    def extract_invoices(page):
        if isinstance(page, list):
            return page, False
        if "data" in page:
            return page["data"], page.get("has_more", False)
        # Try common keys
        for key in ("invoices", "result", "results"):
            if key in page:
                v = page[key]
                if isinstance(v, list):
                    return v, page.get("has_more", False)
        # Fallback: look for a list value
        for k, v in page.items():
            if isinstance(v, list) and len(v) > 0:
                return v, page.get("has_more", False)
        return [], page.get("has_more", False)

    invoices1, _ = extract_invoices(page1)
    invoices2, has_more_p2 = extract_invoices(page2)

    print(f"  Page 1: {len(invoices1)} invoices")
    print(f"  Page 2: {len(invoices2)} invoices, has_more={has_more_p2}")

    # 2. Merge + dedup by invoice ID
    seen_ids = {}
    for inv in invoices1 + invoices2:
        inv_id = inv.get("id")
        if inv_id and inv_id not in seen_ids:
            seen_ids[inv_id] = inv
    all_invoices = list(seen_ids.values())
    print(f"  After merge+dedup: {len(all_invoices)} invoices")
    print(f"\n[CRITICAL] has_more on page 2: {has_more_p2}")

    # 3. Load fixtures
    fixtures = json.loads(FIXTURES.read_text(encoding='utf-8'))
    fx_mrr   = fixtures["mrr_by_team_month_stripe"]
    fx_oneoff= fixtures["oneoff_total_by_month_stripe"]
    fx_total = fixtures["company_mrr_total_stripe"]

    target_mrr    = {team: fx_mrr[team]["may"] for team in fx_mrr}
    target_oneoff = fx_oneoff["may"]
    target_total  = fx_total["may"]

    # 4. Run simulation
    # Results buckets: (stripe_paid_only, all_eligible)
    mrr_stripe   = {}
    mrr_all      = {}
    oneoff_stripe = 0.0
    oneoff_all    = 0.0

    other_lines  = []  # (desc, customer, amount_dollars)
    rescue_found = {}  # customer_name → list of {id, status, teams, created_month}

    # Invoice IDs contributing to each team (for gap debugging)
    mrr_inv_by_team_stripe = {}
    oneoff_invs_stripe = []

    skipped_stats = {"not_eligible": 0, "zero_neg": 0, "ad_spend": 0,
                     "wrong_period": 0, "no_lines": 0}

    for inv in all_invoices:
        inv_id      = inv.get("id", "?")
        status      = inv.get("status", "")
        customer_name = inv.get("customer_name") or inv.get("customer", {}) or ""
        if isinstance(customer_name, dict):
            customer_name = customer_name.get("name", "")
        created_ts  = inv.get("created")

        # Eligibility
        is_rescue = customer_name in OFF_STRIPE_RESCUE
        is_paid   = (status == "paid")
        eligible  = is_paid or is_rescue

        if not eligible:
            skipped_stats["not_eligible"] += 1
            continue

        # Track rescue invoices
        if is_rescue:
            if customer_name not in rescue_found:
                rescue_found[customer_name] = []

        # Get line items
        lines = inv.get("lines", {})
        if isinstance(lines, dict):
            line_items = lines.get("data", [])
        elif isinstance(lines, list):
            line_items = lines
        else:
            line_items = []

        if not line_items:
            skipped_stats["no_lines"] += 1
            continue

        rescue_teams_this_inv = {}

        for line in line_items:
            amount_cents = line.get("amount", 0)
            if amount_cents <= 0:
                skipped_stats["zero_neg"] += 1
                continue

            amount_dollars = amount_cents / 100.0

            # Description
            raw_desc = line.get("description") or ""
            desc_norm = normalize(raw_desc)

            if desc_norm == "Ad Spend Reimbursement":
                skipped_stats["ad_spend"] += 1
                continue

            # Determine line type and period eligibility
            parent = line.get("parent") or {}
            parent_type = parent.get("type", "")

            if parent_type == "subscription_item_details":
                # MRR: use period.start
                period = line.get("period") or {}
                period_start = period.get("start")
                if not period_start or not in_may_2026(period_start):
                    skipped_stats["wrong_period"] += 1
                    continue
                line_kind = "mrr"
            else:
                # One-off (invoice_item_details or unknown): use invoice.created
                if not created_ts or not in_may_2026(created_ts):
                    skipped_stats["wrong_period"] += 1
                    continue
                line_kind = "oneoff"

            team = map_team(desc_norm)

            if team == "Other":
                other_lines.append((raw_desc, desc_norm, customer_name, amount_dollars, inv_id, line_kind))

            # Accumulate — ALL eligible
            if line_kind == "mrr":
                mrr_all[team] = mrr_all.get(team, 0.0) + amount_dollars
            else:
                oneoff_all += amount_dollars

            # Accumulate — Stripe-paid only (exclude rescue by name)
            if not is_rescue:
                if line_kind == "mrr":
                    mrr_stripe[team] = mrr_stripe.get(team, 0.0) + amount_dollars
                    mrr_inv_by_team_stripe.setdefault(team, []).append(
                        (inv_id, customer_name, desc_norm, amount_dollars)
                    )
                else:
                    oneoff_stripe += amount_dollars
                    oneoff_invs_stripe.append(
                        (inv_id, customer_name, desc_norm, amount_dollars)
                    )

            # Track rescue teams
            if is_rescue:
                rescue_teams_this_inv[team] = rescue_teams_this_inv.get(team, 0.0) + amount_dollars

        # Record rescue invoice summary
        if is_rescue and rescue_teams_this_inv:
            created_month = ts_to_dt(created_ts).strftime("%Y-%m") if created_ts else "?"
            rescue_found.setdefault(customer_name, []).append({
                "id": inv_id, "status": status,
                "teams": rescue_teams_this_inv, "created_month": created_month
            })

    # ── Report ────────────────────────────────────────────────────────────────
    all_teams = ["Meta", "Email", "Google", "Social", "Web", "Creative", "SEO", "GHL"]

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\n1. has_more on page 2: {has_more_p2}  {'OK - all data present' if not has_more_p2 else 'WARNING - there are more pages!'}")
    print(f"2. Total invoices after merge+dedup: {len(all_invoices)}")

    print("\n3. MRR BY TEAM (Stripe-paid only) vs Fixture:")
    print(f"   {'Team':<12} {'Computed':>10} {'Fixture':>10} {'Diff':>10}  Result")
    print(f"   {'-'*12} {'-'*10} {'-'*10} {'-'*10}  ------")
    all_mrr_pass = True
    for team in all_teams:
        computed = round(mrr_stripe.get(team, 0.0))
        fixture  = target_mrr.get(team, 0)
        diff     = computed - fixture
        status   = "PASS" if diff == 0 else "FAIL"
        if diff != 0:
            all_mrr_pass = False
        print(f"   {team:<12} {computed:>10,.0f} {fixture:>10,.0f} {diff:>+10,.0f}  {status}")

    mrr_total_stripe = round(sum(mrr_stripe.values()))
    print(f"\n4. Company MRR Total (Stripe-paid only): {mrr_total_stripe:,.0f}  Fixture: {target_total:,.0f}  Diff: {mrr_total_stripe - target_total:+,.0f}  {'PASS' if mrr_total_stripe == target_total else 'FAIL'}")

    oneoff_stripe_r = round(oneoff_stripe)
    print(f"5. One-off Total (Stripe-paid only):     {oneoff_stripe_r:,.0f}  Fixture: {target_oneoff:,.0f}  Diff: {oneoff_stripe_r - target_oneoff:+,.0f}  {'PASS' if oneoff_stripe_r == target_oneoff else 'FAIL'}")

    print(f"\n6. Lines mapped to 'Other' ({len(other_lines)} total):")
    if other_lines:
        for raw_desc, desc_norm, cust, amt, inv_id, kind in other_lines:
            print(f"   [{kind}] ${amt:>8.2f}  {cust:<30}  raw='{raw_desc}'  norm='{desc_norm}'  inv={inv_id}")
    else:
        print("   (none)")

    print(f"\n7. Rescue client invoices found:")
    if rescue_found:
        for name, entries in rescue_found.items():
            if not entries:
                print(f"   {name}: NOT FOUND in data")
            else:
                for e in entries:
                    print(f"   {name}  id={e['id']}  status={e['status']}  created={e['created_month']}  teams={e['teams']}")
    else:
        print("   (none found — rescue clients may not be in the Stripe pull or have no eligible lines)")

    print(f"\n   All eligible MRR (incl rescue):  {round(sum(mrr_all.values())):,.0f}")
    print(f"   All eligible one-off (incl rescue): {round(oneoff_all):,.0f}")
    total_all = round(sum(mrr_all.values()) + oneoff_all)
    print(f"   Total recognized revenue (all eligible): {total_all:,.0f}")

    # 8. Failure gap detail
    print("\n8. Gap Investigation (failing teams):")
    any_fail = False
    for team in all_teams:
        computed = round(mrr_stripe.get(team, 0.0))
        fixture  = target_mrr.get(team, 0)
        diff     = computed - fixture
        if diff != 0:
            any_fail = True
            print(f"\n   Team {team}  diff={diff:+,.0f}")
            invs = mrr_inv_by_team_stripe.get(team, [])
            for inv_id, cust, desc, amt in sorted(invs, key=lambda x: -x[3]):
                print(f"     inv={inv_id}  ${amt:>8.2f}  {cust:<28}  '{desc}'")

    if oneoff_stripe_r != target_oneoff:
        any_fail = True
        print(f"\n   One-off gap ({oneoff_stripe_r - target_oneoff:+,.0f}) — contributing invoices:")
        for inv_id, cust, desc, amt in sorted(oneoff_invs_stripe, key=lambda x: -x[3]):
            print(f"     inv={inv_id}  ${amt:>8.2f}  {cust:<28}  '{desc}'")

    if not any_fail:
        print("   All tests passed — no gaps to investigate.")

    print(f"\n   Skipped line stats: {skipped_stats}")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
