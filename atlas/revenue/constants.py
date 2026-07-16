# Clients who pay by check/ACH and sit past-due in Stripe.
# Their invoices live in Stripe with full line-item detail; we include them
# regardless of Stripe paid status.
# NOTE: Crust Pizza and Holland Law also pay by check but ARE marked paid in
# Stripe, so they appear in normal paid pulls. Do NOT add them here or they
# double-count.
OFF_STRIPE_RESCUE: frozenset[str] = frozenset(
    ["Tejas Brewery", "Giant Texas", "Tejas Beer", "Oceanbox"]
)

# Line items whose normalized description matches this string are pass-through
# ad spend — not agency revenue, no margin. Excluded entirely.
PASS_THROUGH_DESCRIPTION = "Ad Spend Reimbursement"

# Service line → delivery team.
# Keys are normalized descriptions (after stripping quantity prefix and period suffix).
# Values are the canonical team names used throughout Atlas.
SERVICE_TO_TEAM: dict[str, str] = {
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
    "CRM Build": "GHL",
    "Content Shoot": "Creative",
    "Custom Creative": "Creative",
}

KNOWN_TEAMS: tuple[str, ...] = (
    "Meta", "Email", "Google", "Social", "Web", "Creative", "SEO", "GHL"
)
