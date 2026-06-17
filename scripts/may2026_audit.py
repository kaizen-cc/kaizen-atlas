#!/usr/bin/env python3
"""
May 2026 Stripe Revenue Audit
Fixed rules as specified.
"""
import json
import re
from datetime import datetime, timezone
from collections import defaultdict

# ─── CONFIG ────────────────────────────────────────────────────────────────────

PAGE_FILES = [
    r"C:\Users\lozan\.claude\projects\C--Users-lozan-Projects-kaizen-cc\c34c7a91-cbb0-49e3-aab5-2d8e82daf063\tool-results\mcp-bd48e178-6046-4c32-a1a3-a4e872c786ca-stripe_api_read-1781718225726.txt",
    r"C:\Users\lozan\.claude\projects\C--Users-lozan-Projects-kaizen-cc\c34c7a91-cbb0-49e3-aab5-2d8e82daf063\tool-results\mcp-bd48e178-6046-4c32-a1a3-a4e872c786ca-stripe_api_read-1781718672767.txt",
    r"C:\Users\lozan\.claude\projects\C--Users-lozan-Projects-kaizen-cc\c34c7a91-cbb0-49e3-aab5-2d8e82daf063\tool-results\mcp-bd48e178-6046-4c32-a1a3-a4e872c786ca-stripe_api_read-1781726794819.txt",
]

SERVICE_TO_TEAM = {
    "Meta Advertising": "Meta",
    "TikTok Advertising": "Meta",
    "Google Advertising": "Google",
    "Email Marketing": "Email",
    "SMS Marketing": "Email",
    "Organic Social": "Social",
    "Social Media Management": "Social",
    "Organic Social Media Management": "Social",
    "Content Creation": "Social",
    "Website Development": "Web",
    "Creative Package": "Creative",
    "SEO": "SEO",
    "CRM": "GHL",
    "CRM Maintenance": "GHL",
}

OFF_STRIPE_RESCUE = {"Tejas Brewery", "Giant Texas", "Tejas Beer", "Oceanbox"}

FIXTURE_MRR = {
    "Meta": 46825,
    "Email": 23050,
    "Google": 20400,
    "Social": 13750,
    "Web": 6500,
    "Creative": 4000,
    "SEO": 1000,
    "GHL": 625,
}
FIXTURE_MRR_TOTAL = 116150
FIXTURE_ONEOFF_TOTAL = 11325

# May 2026 window
MAY_START = datetime(2026, 5, 1, tzinfo=timezone.utc)
MAY_END   = datetime(2026, 6, 1, tzinfo=timezone.utc)

def ts_in_may(ts):
    if ts is None:
        return False
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return MAY_START <= dt < MAY_END

# ─── NORMALIZATION ──────────────────────────────────────────────────────────────

LEADING_RE  = re.compile(r'^\d+\s*[xX•×]\s*')
TRAILING_RE = re.compile(r'\s*\(at \$[\d,]+\.?\d*\s*/\s*\w+\)\s*$')

def normalize(desc):
    if not desc:
        return ""
    d = LEADING_RE.sub('', desc.strip())
    d = TRAILING_RE.sub('', d).strip()
    return d

def map_team(desc_norm):
    return SERVICE_TO_TEAM.get(desc_norm, "Other")

# ─── LOAD & MERGE ──────────────────────────────────────────────────────────────

invoices = {}  # id -> invoice dict
page3_has_more = None
total_raw = 0

for i, path in enumerate(PAGE_FILES):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    page_invoices = data.get('data', [])
    total_raw += len(page_invoices)
    if i == 2:
        page3_has_more = data.get('has_more', False)
    for inv in page_invoices:
        inv_id = inv['id']
        if inv_id not in invoices:
            invoices[inv_id] = inv

print(f"\n{'='*60}")
print(f" MAY 2026 STRIPE AUDIT")
print(f"{'='*60}")
print(f"\n1. PAGINATION")
print(f"   Page 3 has_more: {page3_has_more}")
print(f"   Raw invoice count across pages: {total_raw}")
print(f"   After dedup: {len(invoices)} unique invoices")

# ─── PROCESS LINES ─────────────────────────────────────────────────────────────

mrr_by_team    = defaultdict(int)   # Stripe-paid only
rescue_mrr     = defaultdict(lambda: defaultdict(int))  # rescue -> team -> cents
oneoff_total   = 0                   # Stripe-paid only, May-created
other_lines    = []
rescue_lines   = []
rescue_oneoff  = 0

for inv in invoices.values():
    status        = inv.get('status', '')
    customer_name = inv.get('customer_name') or ''
    inv_created   = inv.get('created')

    is_paid   = status == 'paid'
    is_rescue = customer_name in OFF_STRIPE_RESCUE

    # Rule 1: eligible if paid OR rescue
    if not (is_paid or is_rescue):
        continue

    lines_data = inv.get('lines', {}).get('data', [])
    for line in lines_data:
        amount = line.get('amount', 0)
        # Rule 3: skip <= 0
        if amount <= 0:
            continue

        desc_raw  = line.get('description') or ''
        desc_norm = normalize(desc_raw)

        # Rule 4: skip Ad Spend Reimbursement
        if desc_norm == "Ad Spend Reimbursement":
            continue

        parent_type = (line.get('parent') or {}).get('type', '')
        period      = line.get('period') or {}

        if parent_type == 'subscription_item_details':
            # Rule 5: include only if period.start in May
            if not ts_in_may(period.get('start')):
                continue
            team = map_team(desc_norm)
            if is_rescue:
                rescue_mrr[customer_name][team] += amount
            else:
                mrr_by_team[team] += amount
                if team == 'Other':
                    other_lines.append({
                        'type': 'MRR',
                        'desc': desc_norm,
                        'raw': desc_raw,
                        'customer': customer_name,
                        'amount_cents': amount,
                        'invoice': inv['id'],
                    })

        elif parent_type == 'invoice_item_details':
            # Rule 6: include only if invoice.created in May
            if not ts_in_may(inv_created):
                continue
            team = map_team(desc_norm)
            if is_rescue:
                rescue_oneoff += amount
            else:
                oneoff_total += amount
                if team == 'Other':
                    other_lines.append({
                        'type': 'OneOff',
                        'desc': desc_norm,
                        'raw': desc_raw,
                        'customer': customer_name,
                        'amount_cents': amount,
                        'invoice': inv['id'],
                    })

# Convert to dollars
def cents(v): return v / 100

# ─── REPORT ────────────────────────────────────────────────────────────────────

print(f"\n2. MRR BY TEAM (Stripe-paid only) vs Fixture")
print(f"   {'Team':<12} {'Got':>10} {'Expected':>10} {'Diff':>10}  Status")
print(f"   {'-'*55}")
all_teams = set(list(FIXTURE_MRR.keys()) + list(mrr_by_team.keys()))
mrr_ok = True
for team in sorted(all_teams):
    got = mrr_by_team.get(team, 0)
    exp = FIXTURE_MRR.get(team, 0)
    diff = got - exp * 100  # exp is in dollars, got is in cents
    status = "PASS" if diff == 0 else "FAIL"
    if status == "FAIL": mrr_ok = False
    print(f"   {team:<12} {cents(got):>10.2f} {exp:>10.2f} {cents(diff):>+10.2f}  {status}")

print(f"\n3. COMPANY MRR TOTAL vs Fixture")
mrr_total_got = sum(mrr_by_team.values())
mrr_total_exp = FIXTURE_MRR_TOTAL * 100
mrr_total_diff = mrr_total_got - mrr_total_exp
mrr_total_ok = mrr_total_diff == 0
print(f"   Got: ${cents(mrr_total_got):,.2f}  Expected: ${FIXTURE_MRR_TOTAL:,.2f}  Diff: ${cents(mrr_total_diff):+,.2f}  {'PASS' if mrr_total_ok else 'FAIL'}")

print(f"\n4. ONE-OFF TOTAL (Stripe-paid only, May-created) vs Fixture")
oneoff_exp = FIXTURE_ONEOFF_TOTAL * 100
oneoff_diff = oneoff_total - oneoff_exp
oneoff_ok = oneoff_diff == 0
print(f"   Got: ${cents(oneoff_total):,.2f}  Expected: ${FIXTURE_ONEOFF_TOTAL:,.2f}  Diff: ${cents(oneoff_diff):+,.2f}  {'PASS' if oneoff_ok else 'FAIL'}")

print(f"\n5. REMAINING 'Other' LINES")
if not other_lines:
    print("   None — all lines mapped cleanly.")
else:
    print(f"   {len(other_lines)} unresolved line(s):")
    for o in other_lines:
        print(f"   [{o['type']}] customer={o['customer']}  amount=${cents(o['amount_cents']):.2f}")
        print(f"          desc_norm={o['desc']!r}")
        print(f"          desc_raw={o['raw']!r}")

print(f"\n6. RESCUE CLIENTS")
for client, teams in rescue_mrr.items():
    total = sum(teams.values())
    print(f"   {client}: total=${cents(total):.2f}")
    for t, v in sorted(teams.items()):
        print(f"     {t}: ${cents(v):.2f}")
if not rescue_mrr:
    print("   No rescue clients found in subscription lines for May.")
if rescue_oneoff:
    print(f"   Rescue one-off (May-created): ${cents(rescue_oneoff):.2f}")

oceanbox_found = "Oceanbox" in rescue_mrr or any(
    inv.get('customer_name') == 'Oceanbox' for inv in invoices.values()
    if inv.get('status') == 'paid' or inv.get('customer_name') in OFF_STRIPE_RESCUE
)
print(f"\n   Oceanbox found in rescue set: {oceanbox_found}")

print(f"\n7. OVERALL VERDICT")
phase1_clean = mrr_ok and mrr_total_ok and oneoff_ok and not other_lines
print(f"   MRR by team:   {'PASS' if mrr_ok else 'FAIL'}")
print(f"   MRR total:     {'PASS' if mrr_total_ok else 'FAIL'}")
print(f"   One-off total: {'PASS' if oneoff_ok else 'FAIL'}")
print(f"   Other lines:   {'CLEAN' if not other_lines else f'DIRTY ({len(other_lines)} lines)'}")
print(f"\n   Phase 1 CLEAN: {'YES (all pass)' if phase1_clean else 'NO - see diffs above'}")
print(f"\n{'='*60}\n")
