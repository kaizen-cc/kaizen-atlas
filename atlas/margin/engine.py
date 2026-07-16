"""Margin engine: Phase 4.

Combines revenue (Phase 1), labor (Phase 2), and software (Phase 3) to produce:
  - Company P&L  (total_revenue − total_labor − total_software)
  - Team contribution margins  (per delivery team)
  - Per-client margins  (end-client level; white-label agencies split by Toggl hours)
"""

from __future__ import annotations

from collections import defaultdict

from atlas.labor.constants import DELIVERY_TEAMS, EXCLUDED_TOGGL_UIDS, ROSTER
from atlas.labor.engine import compute_labor
from atlas.labor.toggl_pull import fetch_projects_with_clients, fetch_user_hours
from atlas.revenue.engine import compute_revenue
from atlas.software.engine import compute_software

from .constants import AGENCY_TO_CLIENTS, AGENCY_CUSTOMERS, WHITE_LABEL_MAP
from .models import ClientMargin, CompanyPL, MarginResult, TeamMargin


def compute_margin(year: int, month: int) -> MarginResult:
    """Compute full margin model for the given month.

    Calls all three sub-engines then joins on team and client dimensions.
    Per-client labor allocation requires a live Toggl API call.
    """
    revenue = compute_revenue(year, month)
    labor = compute_labor(year, month)
    software = compute_software()

    # ── Company P&L ─────────────────────────────────────────────────────────
    total_revenue = revenue.mrr_total + revenue.oneoff_total

    # Delivery + Operations labor (all members in labor result)
    total_labor = sum(m.cost for m in labor.member_details)

    total_software = software.team_total + software.company_total

    company = CompanyPL(
        year=year,
        month=month,
        total_revenue=round(total_revenue, 2),
        total_labor=round(total_labor, 2),
        total_software=round(total_software, 2),
    )

    # ── Team contribution margins ────────────────────────────────────────────
    by_team: dict[str, TeamMargin] = {}
    for team in DELIVERY_TEAMS:
        mrr = revenue.mrr_by_team.get(team, 0.0)
        oneoff = revenue.oneoff_by_team.get(team, 0.0)
        team_labor = labor.labor_by_team.get(team, 0.0)
        team_sw = software.by_team[team].total if team in software.by_team else 0.0
        by_team[team] = TeamMargin(
            team=team,
            mrr=round(mrr, 2),
            oneoff=round(oneoff, 2),
            labor=round(team_labor, 2),
            software=round(team_sw, 2),
        )

    # ── Per-client margins ───────────────────────────────────────────────────
    by_client = _compute_client_margins(revenue, labor, year, month)

    return MarginResult(
        company=company,
        by_team=by_team,
        by_client=by_client,
        low_tracking_flags=[d.name for d in labor.member_details if d.low_tracking_flag],
        unmatched_revenue_lines=revenue.unmatched_lines,
    )


def _compute_client_margins(revenue, labor, year: int, month: int) -> dict[str, ClientMargin]:
    """Compute per-client margins.

    Revenue attribution:
      - Direct client: revenue_by_customer[client_name] (exact Stripe customer match)
      - White-label sub-client: agency revenue split proportionally by Toggl hours

    Labor attribution:
      - For each roster member, their cost is split across clients using the
        fraction of that member's hours logged against each client's projects.
    """
    # Fetch project→client mapping from Toggl
    project_map = fetch_projects_with_clients()  # pid → {client_name, ...}

    # Fetch per-user per-project hours for this month
    user_hours_raw = fetch_user_hours(year, month)

    # Build {uid: {client_name: seconds}}
    uid_client_secs: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in user_hours_raw:
        uid = row["uid"]
        pid = row["project_id"]
        secs = row["seconds"]
        if not pid or not secs:
            continue
        proj = project_map.get(pid)
        if not proj or not proj.get("client_name"):
            continue
        uid_client_secs[uid][proj["client_name"]] += secs

    # Build name → detail lookup from labor result
    detail_by_name = {d.name: d for d in labor.member_details}
    # Build uid → name from roster
    roster_by_uid = {m["toggl_uid"]: m for m in ROSTER if m.get("toggl_uid") and m["toggl_uid"] not in EXCLUDED_TOGGL_UIDS}

    # Compute client-level labor cost: {client_name: cost}
    client_labor: dict[str, float] = defaultdict(float)
    for uid, client_secs in uid_client_secs.items():
        member_info = roster_by_uid.get(uid)
        if not member_info:
            continue
        member_detail = detail_by_name.get(member_info["name"])
        if not member_detail or not member_detail.cost:
            continue

        total_secs = sum(client_secs.values())
        if not total_secs:
            continue

        for client_name, secs in client_secs.items():
            share = secs / total_secs
            client_labor[client_name] += member_detail.cost * share

    # ── Revenue per end-client ───────────────────────────────────────────────
    # Agency sub-client revenue is already resolved in the revenue engine by
    # parsing the invoice description field. revenue_by_customer keys are
    # already end-client names (not agency names) for white-label invoices.
    client_revenue: dict[str, float] = dict(revenue.revenue_by_customer)

    # ── Assemble ClientMargin objects ────────────────────────────────────────
    all_client_names = set(client_revenue) | set(client_labor)
    by_client: dict[str, ClientMargin] = {}
    for name in sorted(all_client_names):
        rev = client_revenue.get(name, 0.0)
        cost = client_labor.get(name, 0.0)
        agency = WHITE_LABEL_MAP.get(name)
        by_client[name] = ClientMargin(
            name=name,
            agency=agency,
            revenue=round(rev, 2),
            labor_cost=round(cost, 2),
        )

    return by_client
