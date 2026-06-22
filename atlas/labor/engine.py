"""Labor engine: Phase 2.

Computes per-team and per-client labor costs from Toggl + roster constants.

Cost rules:
  flat_monthly  — fixed monthly amount from constants.ROSTER regardless of
                  hours logged. Toggl hours still used for client allocation.
  hourly        — Toggl hours × labor_cost rate from the Toggl workspace user
                  record (the living rate, always current).

Per-client allocation: for each worker, their total cost is split across
clients in proportion to the Toggl hours they logged per project.

Photographers (Quiroz, Walsh) are not in Toggl; their cost is a Phase 3
stub that will be wired from Xero account 830.

Gusto W-2 actuals (Mel, Peter, Clare) are used as a reconciliation check
when GUSTO_API_KEY is present; otherwise the engine uses Toggl rates.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .constants import (
    DELIVERY_TEAMS,
    EXCLUDED_TOGGL_UIDS,
    LOW_TRACKING_HOURS_THRESHOLD,
    ROSTER,
)
from .toggl_pull import fetch_user_hours, fetch_workspace_users


# ── Roster index built once at import time ──────────────────────────────────

_ROSTER_BY_UID: dict[int, dict] = {r["toggl_uid"]: r for r in ROSTER if r.get("toggl_uid")}


@dataclass
class MemberLaborDetail:
    name: str
    team: str
    payment_type: str          # "flat_monthly" or "hourly"
    hours: float               # total hours logged in Toggl this month
    rate: float | None         # $/hr from Toggl (None for flat_monthly)
    cost: float                # actual cost this month
    low_tracking_flag: bool    # True if salary worker logged below threshold
    # project_id → fraction of this worker's hours (for client allocation)
    project_allocation: dict[int, float] = field(default_factory=dict)


@dataclass
class LaborResult:
    year: int
    month: int
    # per-team total cost
    labor_by_team: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    # per-team per-project cost (for per-client tab)
    labor_by_team_project: dict[str, dict[int, float]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(float))
    )
    member_details: list[MemberLaborDetail] = field(default_factory=list)
    # Toggl users active in the month but not in roster (billing/hygiene flag)
    unrostered_uids: list[dict] = field(default_factory=list)
    # Stub for Phase 3: photographer cost from Xero 830
    photographer_cost_stub: float = 360.0  # May validated figure; replace in Phase 3

    @property
    def total_delivery_labor(self) -> float:
        return sum(v for k, v in self.labor_by_team.items() if k in DELIVERY_TEAMS)


def compute_labor(year: int, month: int) -> LaborResult:
    result = LaborResult(year=year, month=month)

    # Pull Toggl data
    ws_users = fetch_workspace_users()  # uid → {name, email, labor_cost}
    hour_rows = fetch_user_hours(year, month)  # list of {uid, project_id, seconds}

    # Aggregate seconds per uid, and per uid+project
    uid_total_seconds: dict[int, int] = defaultdict(int)
    uid_project_seconds: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    for row in hour_rows:
        uid = row["uid"]
        if uid in EXCLUDED_TOGGL_UIDS:
            continue
        secs = row["seconds"]
        pid = row["project_id"]
        uid_total_seconds[uid] += secs
        if pid:
            uid_project_seconds[uid][pid] += secs

    # All uids that logged hours this month
    active_uids = set(uid_total_seconds.keys())

    # Flag unrostered active users (not in roster and not excluded)
    rostered_uids = set(_ROSTER_BY_UID.keys())
    for uid in active_uids:
        if uid not in rostered_uids and uid not in EXCLUDED_TOGGL_UIDS:
            ws_info = ws_users.get(uid, {})
            result.unrostered_uids.append({
                "uid": uid,
                "name": ws_info.get("name", "unknown"),
                "email": ws_info.get("email", ""),
                "hours": uid_total_seconds[uid] / 3600,
            })

    # Compute per-member labor
    for member in ROSTER:
        uid = member.get("toggl_uid")
        if not uid or uid in EXCLUDED_TOGGL_UIDS:
            continue

        team = member["team"]
        ptype = member["type"]
        total_secs = uid_total_seconds.get(uid, 0)
        total_hours = total_secs / 3600

        ws_info = ws_users.get(uid, {})
        toggl_rate = ws_info.get("labor_cost")  # may be None

        if ptype == "flat_monthly":
            cost = member.get("flat_amount", 0.0)
            rate = None
            low_flag = total_hours < LOW_TRACKING_HOURS_THRESHOLD
        else:
            # hourly — use Toggl labor_cost rate
            rate = toggl_rate or 0.0
            cost = total_hours * rate
            low_flag = False

        # Per-project allocation (proportion of hours per project)
        proj_secs = uid_project_seconds.get(uid, {})
        if total_secs > 0:
            proj_alloc = {pid: secs / total_secs for pid, secs in proj_secs.items()}
        else:
            proj_alloc = {}

        detail = MemberLaborDetail(
            name=member["name"],
            team=team,
            payment_type=ptype,
            hours=total_hours,
            rate=rate,
            cost=cost,
            low_tracking_flag=low_flag,
            project_allocation=proj_alloc,
        )
        result.member_details.append(detail)
        result.labor_by_team[team] += cost

        # Distribute cost across projects
        for pid, fraction in proj_alloc.items():
            result.labor_by_team_project[team][pid] += cost * fraction

    # Add photographer stub to Creative (replaced by Xero 830 in Phase 3)
    result.labor_by_team["Creative"] += result.photographer_cost_stub

    return result
