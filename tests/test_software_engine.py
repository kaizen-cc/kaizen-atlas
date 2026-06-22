"""Phase 3 software engine tests.

All tests run without Xero credentials — the allocation key is static.
"""

import json
from pathlib import Path

import pytest

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "kaizen_atlas_fixtures.json").read_text()
)

TEAMS = ["Meta", "Creative", "Email", "Web", "Google", "SEO", "GHL", "Social"]


# ── Key integrity ────────────────────────────────────────────────────────────

def test_team_software_total_matches_fixture():
    """Each team's computed total must match the fixture software_breakdown_monthly sum."""
    from atlas.software.constants import TEAM_SOFTWARE_MONTHLY
    breakdown = FIXTURES["software_breakdown_monthly"]

    for team in TEAMS:
        expected = round(sum(amt for _, amt in breakdown[team]), 2)
        actual = TEAM_SOFTWARE_MONTHLY[team]
        assert abs(actual - expected) < 0.02, (
            f"{team} software total: computed ${actual}, fixture sum ${expected}"
        )


def test_seat_share_calculation():
    from atlas.software.constants import CLAUDE_SLACK_RATE_PER_SEAT, SEAT_COUNTS
    # Meta 9 seats × $49.75 = $447.75 → rounds to $447.75; fixture shows $448
    meta_seats = SEAT_COUNTS["Meta"] * CLAUDE_SLACK_RATE_PER_SEAT
    assert abs(meta_seats - 447.75) < 0.01


def test_no_company_bucket_in_team_totals():
    """Operations/Sales/Misc must not appear in delivery team software costs."""
    from atlas.software.constants import TEAM_SOFTWARE_MONTHLY
    assert "Operations" not in TEAM_SOFTWARE_MONTHLY
    assert "Sales" not in TEAM_SOFTWARE_MONTHLY
    assert "Misc" not in TEAM_SOFTWARE_MONTHLY


# ── Engine output ────────────────────────────────────────────────────────────

def test_compute_software_all_teams_present():
    from atlas.software.engine import compute_software
    result = compute_software()
    for team in TEAMS:
        assert team in result.by_team, f"Team {team} missing from software result"


def test_compute_software_totals_match_fixtures():
    from atlas.software.engine import compute_software
    result = compute_software()
    breakdown = FIXTURES["software_breakdown_monthly"]

    for team in TEAMS:
        expected = round(sum(amt for _, amt in breakdown[team]), 2)
        actual = result.by_team[team].total
        assert abs(actual - expected) < 0.02, (
            f"{team}: engine total ${actual}, fixture ${expected}"
        )


def test_compute_software_line_items_match_fixtures():
    """Each team's line items should cover the same products as the fixture breakdown."""
    from atlas.software.engine import compute_software
    result = compute_software()
    breakdown = FIXTURES["software_breakdown_monthly"]

    for team in TEAMS:
        fixture_total = sum(amt for _, amt in breakdown[team])
        engine_line_total = sum(amt for _, amt in result.by_team[team].direct_tools)
        # Line items include the seat share as the last entry — total must match
        assert abs(engine_line_total - fixture_total) < 0.02, (
            f"{team} line item sum ${engine_line_total} != fixture ${fixture_total}"
        )


def test_per_team_may_software_matches_fixtures():
    """per_team_may.software in fixtures must match computed team totals."""
    from atlas.software.engine import compute_software
    result = compute_software()
    per_team_may = FIXTURES["per_team_may"]

    for team in TEAMS:
        expected = per_team_may[team]["software"]
        actual = result.by_team[team].total
        assert abs(actual - expected) < 0.02, (
            f"{team} per_team_may software: engine ${actual}, fixture ${expected}"
        )


def test_xero_not_available_returns_none_actual():
    """Without Xero credentials, xero_actual must be None."""
    import os
    # Ensure no Xero vars are set in this test environment
    for var in ("XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "XERO_TENANT_ID", "XERO_REFRESH_TOKEN"):
        os.environ.pop(var, None)

    from atlas.software.engine import compute_software
    result = compute_software()
    assert result.xero_actual is None
    assert result.xero_residual is None


def test_xero_pull_returns_none_when_unconfigured():
    """fetch_software_spend returns None, not an exception, when Xero is not set up."""
    from atlas.software.xero_pull import fetch_software_spend
    result = fetch_software_spend(2026, 5)
    assert result is None


def test_contractor_pull_returns_none_when_unconfigured():
    from atlas.software.xero_pull import fetch_contractor_payments
    result = fetch_contractor_payments(2026, 5)
    assert result is None
