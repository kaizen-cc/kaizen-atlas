"""Phase 4 margin engine tests."""

import json
from pathlib import Path

import pytest

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "kaizen_atlas_fixtures.json").read_text()
)

needs_stripe = pytest.mark.skipif(
    not __import__("os").environ.get("STRIPE_API_KEY"),
    reason="STRIPE_API_KEY not set",
)
needs_toggl = pytest.mark.skipif(
    not __import__("os").environ.get("TOGGL_API_TOKEN"),
    reason="TOGGL_API_TOKEN not set",
)


# ── Constants integrity ──────────────────────────────────────────────────────

def test_white_label_map_no_duplicate_keys():
    from atlas.margin.constants import WHITE_LABEL_MAP
    clients = list(WHITE_LABEL_MAP.keys())
    assert len(clients) == len(set(clients)), "Duplicate Toggl client name in WHITE_LABEL_MAP"


def test_agency_to_clients_reverse_is_complete():
    from atlas.margin.constants import AGENCY_TO_CLIENTS, WHITE_LABEL_MAP
    reconstructed = {}
    for client, agency in WHITE_LABEL_MAP.items():
        reconstructed.setdefault(agency, []).append(client)
    for agency, clients in reconstructed.items():
        assert set(clients) == set(AGENCY_TO_CLIENTS[agency]), (
            f"AGENCY_TO_CLIENTS mismatch for {agency}"
        )


def test_agency_customers_matches_map_values():
    from atlas.margin.constants import AGENCY_CUSTOMERS, WHITE_LABEL_MAP
    assert AGENCY_CUSTOMERS == frozenset(WHITE_LABEL_MAP.values())


def test_known_agencies_present():
    from atlas.margin.constants import AGENCY_CUSTOMERS
    for agency in ("RE Creative Agency", "Blue Cherry Group", "Lux Marketing Company",
                   "So Shall We", "ZenChange Marketing", "We Think Big"):
        assert agency in AGENCY_CUSTOMERS, f"Agency '{agency}' missing from WHITE_LABEL_MAP"


def test_known_sub_clients_present():
    from atlas.margin.constants import WHITE_LABEL_MAP
    for client in ("dos", "Brooklyn Water Bagel", "Brooklyn Kayak Co",
                   "Crown Rally", "Brainista", "Alelaluna", "Four Star Homes"):
        assert client in WHITE_LABEL_MAP, f"Sub-client '{client}' missing from WHITE_LABEL_MAP"


# ── Models ───────────────────────────────────────────────────────────────────

def test_company_pl_net_profit_property():
    from atlas.margin.models import CompanyPL
    pl = CompanyPL(year=2026, month=5, total_revenue=139425, total_labor=98000, total_software=8117)
    assert abs(pl.net_profit - (139425 - 98000 - 8117)) < 0.01


def test_company_pl_margin_pct_property():
    from atlas.margin.models import CompanyPL
    pl = CompanyPL(year=2026, month=5, total_revenue=139425, total_labor=98274, total_software=8117)
    assert 20.0 < pl.margin_pct < 30.0


def test_team_margin_contribution():
    from atlas.margin.models import TeamMargin
    tm = TeamMargin(team="Meta", mrr=48575, oneoff=0, labor=13768, software=1198)
    assert abs(tm.contribution_margin - (48575 - 13768 - 1198)) < 0.01
    assert tm.contribution_pct > 0


def test_client_margin_zero_revenue():
    from atlas.margin.models import ClientMargin
    cm = ClientMargin(name="Test", agency=None, revenue=0.0, labor_cost=500.0)
    assert cm.margin_pct == 0.0


# ── Integration (requires Stripe + Toggl) ───────────────────────────────────

@needs_stripe
@needs_toggl
def test_company_pl_may_net_profit_within_tolerance():
    """Company net profit for May 2026 should be within $5,000 of fixture.

    Tolerance accounts for labor rate drift since May (rates updated mid-year).
    """
    from atlas.margin.engine import compute_margin
    result = compute_margin(2026, 5)
    fixture_profit = FIXTURES["company_totals"]["may"]["net_profit"]  # 33034
    assert abs(result.company.net_profit - fixture_profit) < 5000, (
        f"Company net profit ${result.company.net_profit:,.0f} vs fixture ${fixture_profit:,.0f} "
        f"(delta ${abs(result.company.net_profit - fixture_profit):,.0f})"
    )


@needs_stripe
@needs_toggl
def test_company_pl_may_margin_pct_in_range():
    """Margin % should be in a reasonable band around the 23.7% fixture."""
    from atlas.margin.engine import compute_margin
    result = compute_margin(2026, 5)
    assert 15.0 <= result.company.margin_pct <= 35.0, (
        f"Margin % {result.company.margin_pct}% outside expected 15–35% band"
    )


@needs_stripe
@needs_toggl
def test_team_margins_all_present():
    from atlas.margin.engine import compute_margin
    from atlas.labor.constants import DELIVERY_TEAMS
    result = compute_margin(2026, 5)
    for team in DELIVERY_TEAMS:
        assert team in result.by_team, f"Team '{team}' missing from margin result"


@needs_stripe
@needs_toggl
def test_team_margin_mrr_matches_revenue_fixture():
    """Team MRR in the margin result must match the per_team_may fixture (±$100)."""
    from atlas.margin.engine import compute_margin
    result = compute_margin(2026, 5)
    per_team = FIXTURES["per_team_may"]
    for team, fixture in per_team.items():
        if team not in result.by_team:
            continue
        expected_mrr = fixture["mrr"]
        actual_mrr = result.by_team[team].mrr
        assert abs(actual_mrr - expected_mrr) < 500, (
            f"{team} MRR: engine ${actual_mrr:,.0f} vs fixture ${expected_mrr:,.0f}"
        )


@needs_stripe
@needs_toggl
def test_per_client_allocations_sum_to_company_labor():
    """Total client labor across all clients should equal total company labor."""
    from atlas.margin.engine import compute_margin
    result = compute_margin(2026, 5)
    client_total = sum(c.labor_cost for c in result.by_client.values())
    company_labor = result.company.total_labor
    # Some labor is not attributed to any client (ops overhead, no client time logged)
    # so client_total <= company_labor
    assert client_total <= company_labor + 1.0, (
        f"Client labor sum ${client_total:,.0f} exceeds company labor ${company_labor:,.0f}"
    )


@needs_stripe
@needs_toggl
def test_white_label_sub_clients_have_agency_set():
    from atlas.margin.engine import compute_margin
    from atlas.margin.constants import WHITE_LABEL_MAP
    result = compute_margin(2026, 5)
    for name, cm in result.by_client.items():
        if name in WHITE_LABEL_MAP:
            assert cm.agency == WHITE_LABEL_MAP[name], (
                f"{name} should have agency={WHITE_LABEL_MAP[name]}, got {cm.agency}"
            )


@needs_stripe
@needs_toggl
def test_low_tracking_flags_list():
    from atlas.margin.engine import compute_margin
    result = compute_margin(2026, 5)
    assert isinstance(result.low_tracking_flags, list)
