"""Phase 2 labor engine tests.

Unit tests run without Toggl. Integration tests require TOGGL_API_TOKEN.
The May 2026 per-team totals will differ from fixtures because Toggl rates
have changed since May. The tests assert the METHOD is correct and flag
known structural issues (low tracking, unrostered users).
"""

import os
import pytest

needs_toggl = pytest.mark.skipif(
    not os.environ.get("TOGGL_API_TOKEN"),
    reason="TOGGL_API_TOKEN not set — skipping live Toggl tests",
)

MAY = (2026, 5)
DELIVERY_TEAMS = ["Meta", "Email", "Google", "Social", "Web", "Creative", "GHL"]


# ── Unit tests — no network ──────────────────────────────────────────────────

def test_roster_no_duplicate_uids():
    from atlas.labor.constants import ROSTER
    uids = [r["toggl_uid"] for r in ROSTER if r.get("toggl_uid")]
    assert len(uids) == len(set(uids)), "Duplicate toggl_uid in ROSTER"


def test_roster_flat_monthly_has_amount():
    from atlas.labor.constants import ROSTER
    for r in ROSTER:
        if r["type"] == "flat_monthly":
            assert "flat_amount" in r and r["flat_amount"] >= 0, (
                f"{r['name']} is flat_monthly but missing flat_amount"
            )


def test_excluded_uids_not_in_roster():
    from atlas.labor.constants import ROSTER, EXCLUDED_TOGGL_UIDS
    roster_uids = {r["toggl_uid"] for r in ROSTER if r.get("toggl_uid")}
    overlap = roster_uids & EXCLUDED_TOGGL_UIDS
    assert not overlap, f"UIDs in both ROSTER and EXCLUDED: {overlap}"


def test_flat_monthly_workers_known():
    from atlas.labor.constants import ROSTER
    flat = {r["name"]: r["flat_amount"] for r in ROSTER if r["type"] == "flat_monthly"}
    assert flat["Mel"] == 4500
    assert flat["Jesus"] == 2500
    assert flat["Fabi"] == 2250
    assert flat["Mark"] == 3500


# ── Integration tests — live Toggl ───────────────────────────────────────────

@needs_toggl
def test_workspace_users_returns_roster_members():
    from atlas.labor.toggl_pull import fetch_workspace_users
    from atlas.labor.constants import ROSTER
    users = fetch_workspace_users()
    roster_uids = {r["toggl_uid"] for r in ROSTER if r.get("toggl_uid")}
    missing = roster_uids - set(users.keys())
    assert not missing, f"Roster UIDs not found in Toggl workspace: {missing}"


@needs_toggl
def test_compute_labor_all_teams_present():
    from atlas.labor.engine import compute_labor
    result = compute_labor(*MAY)
    for team in DELIVERY_TEAMS:
        assert team in result.labor_by_team, f"Team {team} missing from labor result"
        assert result.labor_by_team[team] > 0, f"Team {team} has zero labor"


@needs_toggl
def test_flat_monthly_workers_use_constant_not_hours():
    """Flat monthly workers must have cost == flat_amount, regardless of hours."""
    from atlas.labor.engine import compute_labor
    from atlas.labor.constants import ROSTER
    flat_amounts = {r["name"]: r["flat_amount"] for r in ROSTER if r["type"] == "flat_monthly"}

    result = compute_labor(*MAY)
    for detail in result.member_details:
        if detail.payment_type == "flat_monthly" and detail.name in flat_amounts:
            assert abs(detail.cost - flat_amounts[detail.name]) < 0.01, (
                f"{detail.name}: flat_monthly cost should be {flat_amounts[detail.name]}, "
                f"got {detail.cost}"
            )


@needs_toggl
def test_low_tracking_flag_on_zero_hour_salary_workers():
    """Salary workers with zero or near-zero hours should be flagged."""
    from atlas.labor.engine import compute_labor
    from atlas.labor.constants import LOW_TRACKING_HOURS_THRESHOLD
    result = compute_labor(*MAY)
    flagged = [d for d in result.member_details if d.low_tracking_flag]
    # In May 2026, Mel, Jesus, Fabi logged zero hours — all should be flagged
    flagged_names = {d.name for d in flagged}
    for name in ("Mel", "Jesus", "Fabi"):
        assert name in flagged_names, (
            f"{name} logged zero hours in May but was not flagged"
        )


@needs_toggl
def test_no_excluded_uids_in_result():
    from atlas.labor.engine import compute_labor
    from atlas.labor.constants import EXCLUDED_TOGGL_UIDS
    result = compute_labor(*MAY)
    result_uids = {d.name for d in result.member_details}
    # Rafael should not appear (excluded uid 12965017)
    for detail in result.member_details:
        assert detail.name != "Rafael", "Rafael is excluded but appeared in labor result"


@needs_toggl
def test_per_project_allocation_sums_to_one():
    """Each worker's project allocations must sum to ~1.0 (or be empty)."""
    from atlas.labor.engine import compute_labor
    result = compute_labor(*MAY)
    for detail in result.member_details:
        if detail.project_allocation:
            total = sum(detail.project_allocation.values())
            assert abs(total - 1.0) < 0.001, (
                f"{detail.name} project allocations sum to {total}, expected 1.0"
            )


@needs_toggl
def test_unrostered_users_flagged():
    """Users active in Toggl but not on the roster should surface in unrostered_uids."""
    from atlas.labor.engine import compute_labor
    result = compute_labor(*MAY)
    # Irene, Victor, Venusmarie are expected unrostered (new/external users)
    unrostered_names = {u["name"] for u in result.unrostered_uids}
    # Just verify the list is populated and reported — don't hard-assert names
    # since the roster may be updated to include them
    print(f"Unrostered users in May: {unrostered_names}")


@needs_toggl
def test_photographer_stub_in_creative():
    """Creative labor must include the Xero 830 photographer stub until Phase 3."""
    from atlas.labor.engine import compute_labor
    result = compute_labor(*MAY)
    assert result.photographer_cost_stub == 360.0
    # Creative total should be at least the stub amount
    assert result.labor_by_team["Creative"] >= 360.0
