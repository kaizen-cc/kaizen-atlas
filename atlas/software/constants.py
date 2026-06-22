"""Locked software allocation key.

Source: Kaizen_Software_Allocation_Key.md, validated Jan–May 2026.
These figures are static until software is added/dropped or seat counts change.
Do not edit without updating the allocation key doc.

All amounts are USD/month.
"""

# ── Seat-based allocation ────────────────────────────────────────────────────
# Claude + Slack pooled across 29 seats at $49.75/seat/month.
# 4 company seats (Santi, Kyle, Ryan, Jorgi) stay in Operations.
CLAUDE_SLACK_RATE_PER_SEAT: float = 49.75

SEAT_COUNTS: dict[str, int] = {
    "Meta":       9,
    "Email":      7,
    "Creative":   3,
    "Web":        3,
    "Google":     2,
    "Social":     1,
    "Operations": 4,   # company seats — stays at company level
}

# Actual seat-share amounts from the Claude+Slack invoice, validated against
# the allocation key. These differ slightly from SEAT_COUNTS × $49.75 due to
# invoice-level rounding — use these values, not the computed product.
SEAT_SHARE_ACTUAL: dict[str, float] = {
    "Meta":       448.0,
    "Email":      348.0,
    "Creative":   149.0,
    "Web":        149.0,
    "Google":      99.0,
    "Social":      50.0,
    "SEO":          0.0,
    "GHL":          0.0,
}

# ── Direct tool costs per team ($/month) ────────────────────────────────────
DIRECT_TOOLS: dict[str, list[tuple[str, float]]] = {
    "Meta": [
        ("Deal.ai",              124.00),
        ("Motion (50%)",         404.00),   # shared 50/50 with Creative
        ("Supermetrics (50%)",   222.00),   # shared 50/50 with Google
    ],
    "Creative": [
        ("Motion (50%)",         404.00),
        ("Design · Adobe/Canva/stock", 184.00),
        ("AI media · Arcads/Higgsfield/+3", 151.00),
    ],
    "Email": [
        ("Figma",                302.00),
        ("EmailLove",             35.00),
    ],
    "Web": [
        ("Hosting · GoDaddy/Hostinger/WP", 224.00),
    ],
    "Google": [
        ("Spyfu",                 39.00),
        ("Supermetrics (50%)",   222.00),
    ],
    "SEO": [
        ("Conversion / Seona.ai", 195.00),
        ("Bulls Eye Media",         7.00),
    ],
    "GHL": [
        ("GoHighLevel",           136.00),
    ],
    "Social": [],   # no dedicated direct tools; seat share only
}

# ── Company-level buckets (do NOT flow into team margin) ────────────────────
COMPANY_SOFTWARE: dict[str, float] = {
    "Operations":    2906.00,   # OS dev stack + cross-cutting tools + 4 company seats
    "Sales":         1216.00,   # Riverside, Instantly, internal GHL, Referral Partner Academy
    "Misc":           103.00,   # Spotify, Surf Shark, Buzzsprout, etc.
}

# One-time item excluded from run-rate
ONE_TIME_EXCLUDED: dict[str, float] = {
    "Diiiploy AI (OS build)": 6666.00,
}

# Reclassified out of software entirely (payment rail, not a tool)
RECLASSED_TO_LABOR: dict[str, float] = {
    "Remitly": 271.00,
}

# Klaviyo nets negative in the Softwares account (reimbursements + referral income).
# Internal Klaviyo is Sales/outreach. Negative balance is noted but not subtracted
# from team software costs (it's really income; tracked separately in Phase 5).
KLAVIYO_NOTE = (
    "Klaviyo nets negative in Xero account 835 due to campaign reimbursements "
    "and referral fees. Treated as Sales/outreach income, not a team software credit."
)


def team_software_total(team: str) -> float:
    """Compute monthly software cost for a delivery team from the locked key."""
    seat_share = SEAT_SHARE_ACTUAL.get(team, 0.0)
    direct = sum(amt for _, amt in DIRECT_TOOLS.get(team, []))
    return round(seat_share + direct, 2)


# Pre-computed totals for quick lookup — matches software_breakdown_monthly fixtures
TEAM_SOFTWARE_MONTHLY: dict[str, float] = {
    team: team_software_total(team)
    for team in ("Meta", "Creative", "Email", "Web", "Google", "SEO", "GHL", "Social")
}
