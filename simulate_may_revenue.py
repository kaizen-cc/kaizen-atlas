"""Simulate May 2026 revenue engine computation from Stripe API response."""

import json
import re
import datetime
from collections import defaultdict

STRIPE_FILE = r"C:\Users\lozan\.claude\projects\C--Users-lozan-Projects-kaizen-cc\c34c7a91-cbb0-49e3-aab5-2d8e82daf063\tool-results\mcp-bd48e178-6046-4c32-a1a3-a4e872c786ca-stripe_api_read-1781717907825.txt"

# Constants from engine
OFF_STRIPE_RESCUE = frozenset(["Tejas Brewery", "Giant Texas", "Tejas Beer", "Oceanbox"])
PASS_THROUGH_DESCRIPTION = "Ad Spend Reimbursement"
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

FIXTURE_MRR = {
    "Meta": 46825, "Email": 23050, "Google": 20400,
    "Social": 13750, "Web": 6500, "Creative": 4000,
    "SEO": 1000, "GHL": 625
}
FIXTURE_ONEOFF = 11325
FIXTURE_MRR_TOTAL = 116150

# Normalizer
_QTY_PREFIX = re.compile(r"^\d+\s*[xX]\s*")
_PERIOD_SUFFIX = re.compile(r"\s*\(at \$[\d,]+\.?\d*\s*/\s*\w+\)\s*$")

def normalize(desc):
    s = _QTY_PREFIX.sub("", desc.strip())
    s = _PERIOD_SUFFIX.sub("", s).strip()
    return s

def is_pass_through(desc):
    return normalize(desc) == PASS_THROUGH_DESCRIPTION

def map_to_team(desc):
    return SERVICE_TO_TEAM.get(normalize(desc), "Other")

def customer_name(inv):
    return (inv.get("customer_name") or "").strip()

def is_eligible(inv):
    if inv.get("status") == "paid":
        return True
    return customer_name(inv) in OFF_STRIPE_RESCUE

def subscription_period_month(line):
    period = line.get("period")
    if not period or not period.get("start"):
        return None
    dt = datetime.datetime.fromtimestamp(period["start"], tz=datetime.timezone.utc)
    return dt.year, dt.month

def line_type(line):
    parent = line.get("parent") or {}
    if parent.get("type") == "subscription_item_details":
        return "subscription"
    return "oneoff"

# Load data
print("Loading Stripe response...")
with open(STRIPE_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

invoices = data.get("data", [])
has_more = data.get("has_more", False)
print(f"Total invoices in response: {len(invoices)}")
print(f"has_more: {has_more}")

YEAR, MONTH = 2026, 5

# Simulate engine
seen_ids = set()
mrr_stripe = defaultdict(float)
oneoff_stripe = defaultdict(float)
mrr_rescue = defaultdict(float)
oneoff_rescue = defaultdict(float)
unmatched = []
rescue_invoices = []
off_period_lines = []

total_eligible = 0
ineligible_count = 0

for inv in invoices:
    inv_id = inv.get("id", "")
    if inv_id in seen_ids:
        continue
    if not is_eligible(inv):
        ineligible_count += 1
        continue
    total_eligible += 1
    seen_ids.add(inv_id)

    cname = customer_name(inv)
    is_rescue = cname in OFF_STRIPE_RESCUE

    lines_data = inv.get("lines") or {}
    lines = lines_data.get("data") if isinstance(lines_data, dict) else []
    if not lines:
        continue

    rescue_line_splits = defaultdict(float)

    for line in lines:
        amount_cents = line.get("amount", 0)
        if amount_cents <= 0:
            continue

        description = line.get("description") or ""
        if is_pass_through(description):
            continue

        team = map_to_team(description)
        amount_dollars = amount_cents / 100.0
        lt = line_type(line)

        if lt == "subscription":
            period_ym = subscription_period_month(line)
            if period_ym and period_ym == (YEAR, MONTH):
                if is_rescue:
                    mrr_rescue[team] += amount_dollars
                    rescue_line_splits[team] += amount_dollars
                else:
                    mrr_stripe[team] += amount_dollars
            elif period_ym and period_ym != (YEAR, MONTH):
                off_period_lines.append({
                    "invoice_id": inv_id,
                    "customer": cname,
                    "description": description,
                    "amount": amount_dollars,
                    "period_ym": period_ym,
                })
        else:
            if is_rescue:
                oneoff_rescue[team] += amount_dollars
                rescue_line_splits[team] += amount_dollars
            else:
                oneoff_stripe[team] += amount_dollars

        if team == "Other":
            unmatched.append({
                "invoice_id": inv_id,
                "customer": cname,
                "description": description,
                "normalized": normalize(description),
                "amount": amount_dollars,
                "type": lt,
                "is_rescue": is_rescue,
            })

    if is_rescue:
        rescue_invoices.append({
            "customer": cname,
            "invoice_id": inv_id,
            "status": inv.get("status"),
            "splits": dict(rescue_line_splits),
            "total": sum(rescue_line_splits.values()),
        })

# ---- Report ----
print(f"\n{'='*60}")
print(f"ELIGIBILITY")
print(f"{'='*60}")
print(f"Total invoices: {len(invoices)}")
print(f"Eligible (paid + rescue): {total_eligible}")
print(f"Ineligible (skipped): {ineligible_count}")

print(f"\n{'='*60}")
print(f"has_more: {has_more}  {'*** WARNING: MISSING DATA ***' if has_more else 'OK - full dataset'}")
print(f"{'='*60}")

print(f"\n{'='*60}")
print(f"MRR BY TEAM (Stripe-paid only, excl. rescue) vs FIXTURE")
print(f"{'='*60}")
all_teams = sorted(set(list(FIXTURE_MRR.keys()) + list(mrr_stripe.keys())))
computed_mrr_total = 0
for team in all_teams:
    computed = round(mrr_stripe.get(team, 0))
    fixture = FIXTURE_MRR.get(team, 0)
    diff = computed - fixture
    diff_str = f"+{diff}" if diff > 0 else str(diff)
    flag = " ***" if abs(diff) > 0 else ""
    computed_mrr_total += computed
    print(f"  {team:<10} computed={computed:>8}  fixture={fixture:>8}  diff={diff_str:>8}{flag}")

print(f"\n  TOTAL MRR (computed): {computed_mrr_total}")
print(f"  TOTAL MRR (fixture):  {FIXTURE_MRR_TOTAL}")
print(f"  DIFF: {computed_mrr_total - FIXTURE_MRR_TOTAL}")

print(f"\n{'='*60}")
print(f"ONE-OFF TOTAL (Stripe-paid only, excl. rescue) vs FIXTURE")
print(f"{'='*60}")
computed_oneoff = round(sum(oneoff_stripe.values()))
print(f"  Computed one-off: {computed_oneoff}")
print(f"  Fixture one-off:  {FIXTURE_ONEOFF}")
print(f"  Diff: {computed_oneoff - FIXTURE_ONEOFF}")
if oneoff_stripe:
    print(f"  One-off by team:")
    for team, amt in sorted(oneoff_stripe.items(), key=lambda x: -x[1]):
        print(f"    {team}: ${amt:.2f}")

print(f"\n{'='*60}")
print(f"UNMATCHED LINES (team=Other)")
print(f"{'='*60}")
if not unmatched:
    print("  None.")
else:
    for u in unmatched:
        rescue_tag = " [RESCUE]" if u["is_rescue"] else ""
        print(f"  {u['customer']}{rescue_tag} | '{u['description']}' -> normalized='{u['normalized']}' | ${u['amount']:.2f} | {u['type']}")

print(f"\n{'='*60}")
print(f"RESCUE CLIENT INVOICES")
print(f"{'='*60}")
if not rescue_invoices:
    print("  None found.")
else:
    for ri in rescue_invoices:
        print(f"  {ri['customer']} | {ri['invoice_id']} | status={ri['status']} | total=${ri['total']:.2f}")
        for team, amt in sorted(ri['splits'].items()):
            print(f"    {team}: ${amt:.2f}")

print(f"\n{'='*60}")
print(f"OFF-PERIOD SUBSCRIPTION LINES (period != May 2026)")
print(f"{'='*60}")
if not off_period_lines:
    print("  None.")
else:
    for op in off_period_lines:
        print(f"  {op['customer']} | {op['invoice_id']} | '{op['description']}' | ${op['amount']:.2f} | period={op['period_ym']}")

print(f"\n{'='*60}")
print(f"RESCUE CLIENT REVENUE SUMMARY")
print(f"{'='*60}")
all_rescue_mrr = dict(mrr_rescue)
all_rescue_oneoff = dict(oneoff_rescue)
print(f"  MRR by team (rescue): {dict(all_rescue_mrr)}")
print(f"  One-off by team (rescue): {dict(all_rescue_oneoff)}")
print(f"  Rescue MRR total: ${sum(all_rescue_mrr.values()):.2f}")
print(f"  Rescue one-off total: ${sum(all_rescue_oneoff.values()):.2f}")

print(f"\nDone.")
