"""Phase 1 acceptance tests: assert the revenue engine against validated fixtures.

These tests hit the live Stripe API (read-only). They are skipped automatically
if STRIPE_API_KEY is not set so CI without secrets does not fail.

Run:
    pytest tests/test_revenue_engine.py -v
"""

import json
import os
from pathlib import Path

import pytest

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "kaizen_atlas_fixtures.json"

with open(FIXTURES_PATH) as f:
    FIXTURES = json.load(f)

MONTHS = ["jan", "feb", "mar", "apr", "may"]
MONTH_NUMS = {m: i + 1 for i, m in enumerate(MONTHS)}
YEAR = 2026

TEAMS = ["Meta", "Email", "Google", "Social", "Web", "Creative", "SEO", "GHL"]

needs_stripe = pytest.mark.skipif(
    not os.environ.get("STRIPE_API_KEY"),
    reason="STRIPE_API_KEY not set — skipping live Stripe tests",
)


@pytest.fixture(scope="module")
def revenue_results():
    """Pull and cache all five months so each test doesn't re-fetch."""
    from atlas.revenue.engine import compute_revenue

    return {m: compute_revenue(YEAR, MONTH_NUMS[m]) for m in MONTHS}


# ---------------------------------------------------------------------------
# MRR by team — Stripe-only figures (rescue clients not included in fixture)
# ---------------------------------------------------------------------------

@needs_stripe
@pytest.mark.parametrize("month", MONTHS)
@pytest.mark.parametrize("team", TEAMS)
def test_mrr_by_team(revenue_results, month, team):
    expected = FIXTURES["mrr_by_team_month_stripe"][team][month]
    actual = revenue_results[month].mrr_by_team.get(team, 0.0)
    assert round(actual) == expected, (
        f"MRR mismatch {team} {month.upper()} {YEAR}: "
        f"got ${actual:,.2f}, expected ${expected:,.2f}"
    )


# ---------------------------------------------------------------------------
# Company MRR total (sum across all teams)
# ---------------------------------------------------------------------------

@needs_stripe
@pytest.mark.parametrize("month", MONTHS)
def test_company_mrr_total(revenue_results, month):
    expected = FIXTURES["company_mrr_total_stripe"][month]
    actual = revenue_results[month].mrr_total
    assert round(actual) == expected, (
        f"Company MRR total mismatch {month.upper()} {YEAR}: "
        f"got ${actual:,.2f}, expected ${expected:,.2f}"
    )


# ---------------------------------------------------------------------------
# One-off total (all manual line items, all teams)
# ---------------------------------------------------------------------------

@needs_stripe
@pytest.mark.parametrize("month", MONTHS)
def test_oneoff_total(revenue_results, month):
    expected = FIXTURES["oneoff_total_by_month_stripe"][month]
    actual = revenue_results[month].oneoff_total
    assert round(actual) == expected, (
        f"One-off total mismatch {month.upper()} {YEAR}: "
        f"got ${actual:,.2f}, expected ${expected:,.2f}"
    )


# ---------------------------------------------------------------------------
# Unmatched lines — surfaces billing-hygiene issues, not an assertion failure,
# but prints them so you can see what landed in "Other"
# ---------------------------------------------------------------------------

@needs_stripe
@pytest.mark.parametrize("month", MONTHS)
def test_no_unmatched_lines(revenue_results, month):
    unmatched = revenue_results[month].unmatched_lines
    if unmatched:
        lines = "\n".join(
            f"  {u['customer']} | {u['description']} | ${u['amount']:,.2f}"
            for u in unmatched
        )
        pytest.fail(
            f"Unmatched line items in {month.upper()} {YEAR} "
            f"(landed in 'Other' — add to SERVICE_TO_TEAM or investigate):\n{lines}"
        )


# ---------------------------------------------------------------------------
# Classifier unit tests — no Stripe required
# ---------------------------------------------------------------------------

def test_normalize_strips_quantity_prefix():
    from atlas.revenue.classifier import normalize
    assert normalize("3 x Meta Advertising (at $750.00 / month)") == "Meta Advertising"


def test_normalize_strips_bullet_prefix():
    # Stripe uses U+2022 bullet as quantity separator, not letter x
    from atlas.revenue.classifier import normalize
    assert normalize("1 • Meta Advertising (at $875.00 / month)") == "Meta Advertising"


def test_normalize_strips_period_suffix():
    from atlas.revenue.classifier import normalize
    assert normalize("Email Marketing (at $1,500.00 / month)") == "Email Marketing"


def test_normalize_plain_description():
    from atlas.revenue.classifier import normalize
    assert normalize("Website Development") == "Website Development"


def test_pass_through_detected():
    from atlas.revenue.classifier import is_pass_through
    assert is_pass_through("Ad Spend Reimbursement") is True
    assert is_pass_through("2 x Ad Spend Reimbursement") is True
    assert is_pass_through("Meta Advertising") is False


def test_tiktok_maps_to_meta():
    from atlas.revenue.classifier import map_to_team
    assert map_to_team("TikTok Advertising") == "Meta"


def test_sms_maps_to_email():
    from atlas.revenue.classifier import map_to_team
    assert map_to_team("SMS Marketing") == "Email"


def test_content_creation_maps_to_social():
    from atlas.revenue.classifier import map_to_team
    assert map_to_team("Content Creation") == "Social"


def test_organic_social_media_management_maps_to_social():
    # Stripe uses the compound phrase, not the two separate keys
    from atlas.revenue.classifier import map_to_team
    assert map_to_team("Organic Social Media Management") == "Social"
    assert map_to_team("1 • Organic Social Media Management (at $750.00 / month)") == "Social"


def test_unknown_maps_to_other():
    from atlas.revenue.classifier import map_to_team
    assert map_to_team("Something Unknown") == "Other"
