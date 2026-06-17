"""
May 2026 Revenue Simulation
Compares Stripe invoice data against kaizen_atlas_fixtures.json targets.
"""

import json
import re
import datetime
from collections import defaultdict

# ── Paths ──────────────────────────────────────────────────────────────────────
STRIPE_PATH = (
    r"C:\Users\lozan\.claude\projects\C--Users-lozan-Projects-kaizen-cc"
    r"\c34c7a91-cbb0-49e3-aab5-2d8e82daf063\tool-results"
    r"\mcp-bd48e178-6046-4c32-a1a3-a4e872c786ca-stripe_api_read-1781718225726.txt"
)
FIXTURES_PATH = r"C:\Users\lozan\Projects\kaizen-atlas\tests\fixtures\kaizen_atlas_fixtures.json"

# ── Normalization regexes ──────────────────────────────────────────────────────
RE_PREFIX = re.compile(r"^\d+\s*[xX•]\s*")        # leading "3x ", "2• ", etc.
RE_SUFFIX = re.compile(r"\s*\(at \$[\d,]+\.?\d*\s*/\s*\w+\)\s*$")  # "(at $500/mo)"

# ── Service → Team mapping ────────────────────────────────────────────────────
SERVICE_TO_TEAM = {
    "Meta Advertising": "Meta",
    "TikTok Advertising": "Meta",
    "Google Advertising": "Google",
    "Email Marketing": "Email",
    "SMS Marketing": "Email",
    "Organic Social": "Social",
    "Social Media Management": "Social",
    "Content Creation": "Social",
    "Website Development": "Web",
    "Creative Package": "Creative",
    "SEO": "SEO",
    "CRM": "GHL",
    "CRM Maintenance": "GHL",
}

# ── Off-Stripe rescue clients ─────────────────────────────────────────────────
OFF_STRIPE_RESCUE = {"Tejas Brewery", "Giant Texas", "Tejas Beer", "Oceanbox"}

MAY_YEAR_MONTH = (2026, 5)


def normalize(desc: str) -> str:
    if desc is None:
        return ""
    d = RE_PREFIX.sub("", desc.strip())
    d = RE_SUFFIX.sub("", d)
    return d.strip()


def map_team(desc: str) -> str:
    for svc, team in SERVICE_TO_TEAM.items():
        if svc.lower() in desc.lower():
            return team
    return "Other"


def unix_ym(ts: int):
    dt = datetime.datetime.utcfromtimestamp(ts)
    return (dt.year, dt.month)


def main():
    with open(STRIPE_PATH) as f:
        stripe = json.load(f)
    with open(FIXTURES_PATH) as f:
        fixtures = json.load(f)

    has_more = stripe["has_more"]
    invoices_raw = stripe["data"]
    print(f"=== PULL METADATA ===")
    print(f"has_more: {has_more}")
    print(f"Total invoices in pull: {len(invoices_raw)}")
    if has_more:
        print("WARNING: has_more=True — this pull is INCOMPLETE (only the 100 most recent invoices).")
        print("         May 2026 paid invoices are on subsequent pages; fixture comparisons will show")
        print("         large negative diffs until all pages are fetched and merged.")
    print()

    # ── Pull diagnostics ─────────────────────────────────────────────────────
    from collections import Counter
    status_dist = Counter(inv["status"] for inv in invoices_raw)
    created_dist = Counter(
        datetime.datetime.utcfromtimestamp(inv["created"]).strftime("%Y-%m")
        for inv in invoices_raw
    )
    print("Status distribution in pull:", dict(status_dist))
    print("Created-month distribution:", dict(sorted(created_dist.items())))
    print()

    # ── Dedup by invoice ID ───────────────────────────────────────────────────
    seen_ids = set()
    invoices = []
    for inv in invoices_raw:
        if inv["id"] not in seen_ids:
            seen_ids.add(inv["id"])
            invoices.append(inv)

    # ── Categorise lines ─────────────────────────────────────────────────────
    # Stripe-paid only (no rescue)
    mrr_stripe = defaultdict(float)        # team -> cents
    oneoff_stripe = 0.0                    # cents
    other_lines = []                       # (desc, customer, amount_dollars)
    sub_filtered_count = 0                 # subscription lines NOT in May

    # All eligible (incl rescue)
    mrr_all = defaultdict(float)
    rescue_breakdown = defaultdict(lambda: defaultdict(float))  # client -> team -> cents
    rescue_invoice_info = []

    for inv in invoices:
        status = inv.get("status")
        cname = inv.get("customer_name") or ""
        inv_id = inv["id"]
        inv_created_ym = unix_ym(inv["created"])

        is_rescue = cname in OFF_STRIPE_RESCUE
        is_paid = status == "paid"
        is_eligible = is_paid or is_rescue

        if not is_eligible:
            continue

        for line in inv["lines"]["data"]:
            amount = line.get("amount", 0)
            if amount <= 0:
                continue

            raw_desc = line.get("description") or ""
            desc = normalize(raw_desc)

            if desc == "Ad Spend Reimbursement":
                continue

            parent = line.get("parent") or {}
            parent_type = parent.get("type")
            period = line.get("period") or {}

            if parent_type == "subscription_item_details":
                period_start = period.get("start")
                if period_start is None:
                    sub_filtered_count += 1
                    continue
                period_ym = unix_ym(period_start)
                if period_ym != MAY_YEAR_MONTH:
                    sub_filtered_count += 1
                    continue
                # In May subscription line — MRR
                team = map_team(desc)
                if not is_rescue:
                    mrr_stripe[team] += amount
                    if team == "Other":
                        other_lines.append((raw_desc, cname, amount / 100))
                else:
                    mrr_all[team] += amount
                    rescue_breakdown[cname][team] += amount

            elif parent_type == "invoice_item_details" or parent_type is None:
                # One-off: invoice created in May 2026
                if inv_created_ym != MAY_YEAR_MONTH:
                    continue
                team = map_team(desc)
                if not is_rescue:
                    oneoff_stripe += amount
                    if team == "Other":
                        other_lines.append((raw_desc, cname, amount / 100))
                else:
                    rescue_breakdown[cname][team] += amount
                    if team == "Other":
                        other_lines.append((raw_desc, cname, amount / 100))

            else:
                # Unknown parent type — treat as one-off but log
                if inv_created_ym != MAY_YEAR_MONTH:
                    continue
                team = map_team(desc)
                if not is_rescue:
                    oneoff_stripe += amount
                    other_lines.append((raw_desc, cname, amount / 100))

    # Track rescue client invoices for reporting
    for inv in invoices:
        cname = inv.get("customer_name") or ""
        if cname in OFF_STRIPE_RESCUE:
            rescue_invoice_info.append({
                "client": cname,
                "invoice_id": inv["id"],
                "status": inv["status"],
                "created_ym": unix_ym(inv["created"]),
            })

    # ── Convert to dollars ────────────────────────────────────────────────────
    mrr_stripe_dollars = {k: v / 100 for k, v in mrr_stripe.items()}
    mrr_all_dollars = {k: v / 100 for k, v in mrr_all.items()}
    oneoff_stripe_dollars = oneoff_stripe / 100
    mrr_total_stripe = sum(mrr_stripe_dollars.values())

    # ── Fixture targets ───────────────────────────────────────────────────────
    fix_mrr = fixtures["mrr_by_team_month_stripe"]
    fix_teams = ["Meta", "Email", "Google", "Social", "Web", "Creative", "SEO", "GHL"]
    fix_mrr_may = {t: fix_mrr[t]["may"] for t in fix_teams}
    fix_total = fixtures["company_mrr_total_stripe"]["may"]
    fix_oneoff = fixtures["oneoff_total_by_month_stripe"]["may"]

    # ── Report ────────────────────────────────────────────────────────────────
    print("=== MRR BY TEAM (Stripe-paid only) vs FIXTURE ===")
    print(f"{'Team':<12} {'Computed':>10} {'Fixture':>10} {'Diff':>10}")
    print("-" * 46)
    for team in fix_teams:
        computed = mrr_stripe_dollars.get(team, 0.0)
        fixture = fix_mrr_may[team]
        diff = computed - fixture
        flag = "  <-- MISMATCH" if abs(diff) > 0.01 else ""
        print(f"{team:<12} {computed:>10,.2f} {fixture:>10,.2f} {diff:>+10,.2f}{flag}")
    print()

    print("=== COMPANY MRR TOTAL (Stripe-paid only) ===")
    diff_total = mrr_total_stripe - fix_total
    print(f"Computed: ${mrr_total_stripe:,.2f}")
    print(f"Fixture:  ${fix_total:,.2f}")
    print(f"Diff:     ${diff_total:+,.2f}")
    print()

    print("=== ONE-OFF TOTAL (Stripe-paid, May-created invoices) ===")
    diff_oneoff = oneoff_stripe_dollars - fix_oneoff
    print(f"Computed: ${oneoff_stripe_dollars:,.2f}")
    print(f"Fixture:  ${fix_oneoff:,.2f}")
    print(f"Diff:     ${diff_oneoff:+,.2f}")
    print()

    print("=== LINES LANDING IN 'OTHER' (after normalization) ===")
    if other_lines:
        for raw_desc, cname, amt in other_lines:
            print(f"  Customer: {cname!r:<35} Amount: ${amt:>8,.2f}  Desc: {raw_desc!r}")
    else:
        print("  None — all lines mapped to a known team.")
    print()

    print("=== RESCUE CLIENT BREAKDOWN ===")
    if rescue_invoice_info:
        seen_rescue = set()
        for info in rescue_invoice_info:
            key = info["invoice_id"]
            if key not in seen_rescue:
                seen_rescue.add(key)
                print(f"  Client: {info['client']:<20} Invoice: {info['invoice_id']}  "
                      f"Status: {info['status']:<10} Created: {info['created_ym']}")
        print()
        print("  Revenue splits (rescue clients, by team):")
        for client, teams in rescue_breakdown.items():
            total_c = sum(teams.values()) / 100
            print(f"    {client}:  total=${total_c:,.2f}")
            for team, cents in sorted(teams.items()):
                print(f"      {team}: ${cents/100:,.2f}")
    else:
        print("  No rescue client invoices found in this pull (status != paid, "
              "check if they appear at all).")
        # Show any rescue invoices with any status
        all_rescue = [inv for inv in invoices if (inv.get("customer_name") or "") in OFF_STRIPE_RESCUE]
        if all_rescue:
            print("  Rescue invoices found (any status):")
            for inv in all_rescue:
                print(f"    {inv['customer_name']:<20} {inv['id']}  status={inv['status']}  created_ym={unix_ym(inv['created'])}")
        else:
            print("  No rescue client invoices found in pull at all.")
    print()

    print("=== SUBSCRIPTION LINES FILTERED OUT (period NOT May 2026) ===")
    print(f"  Count: {sub_filtered_count}")
    print()

    print("=== SUMMARY ===")
    all_good = True
    for team in fix_teams:
        computed = mrr_stripe_dollars.get(team, 0.0)
        fixture = fix_mrr_may[team]
        if abs(computed - fixture) > 0.01:
            all_good = False
            break
    if abs(mrr_total_stripe - fix_total) > 0.01:
        all_good = False
    if abs(oneoff_stripe_dollars - fix_oneoff) > 0.01:
        all_good = False
    if all_good:
        print("  ALL targets match fixtures exactly.")
    else:
        print("  Some targets do NOT match — see diffs above.")


if __name__ == "__main__":
    main()
