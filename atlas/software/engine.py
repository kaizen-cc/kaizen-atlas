"""Software engine: Phase 3.

Returns per-team software costs from the locked allocation key.
When Xero credentials are available, cross-references against the live
account 835 (Softwares) transactions for reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
    COMPANY_SOFTWARE,
    DIRECT_TOOLS,
    SEAT_COUNTS,
    SEAT_SHARE_ACTUAL,
    TEAM_SOFTWARE_MONTHLY,
)


@dataclass
class TeamSoftwareDetail:
    team: str
    seat_share: float
    direct_tools: list[tuple[str, float]]   # (product_name, amount)
    total: float


@dataclass
class SoftwareResult:
    # Per delivery team — these flow into contribution margin
    by_team: dict[str, TeamSoftwareDetail] = field(default_factory=dict)
    # Company-level buckets — do NOT touch team margin
    company_level: dict[str, float] = field(default_factory=dict)
    # Xero 835 actual spend this month (None until Xero is wired in Phase 5)
    xero_actual: float | None = None
    # Residual between key total and Xero actual (None until Xero wired)
    xero_residual: float | None = None

    @property
    def team_total(self) -> float:
        return sum(d.total for d in self.by_team.values())

    @property
    def company_total(self) -> float:
        return sum(self.company_level.values())


def compute_software() -> SoftwareResult:
    """Compute monthly software costs from the locked allocation key.

    This is month-invariant — the key is static until tools are added/removed.
    When Xero pull is wired (Phase 5), call with xero_actual to get residual.
    """
    result = SoftwareResult(company_level=dict(COMPANY_SOFTWARE))

    for team in ("Meta", "Creative", "Email", "Web", "Google", "SEO", "GHL", "Social"):
        seat_share = SEAT_SHARE_ACTUAL.get(team, 0.0)
        direct = list(DIRECT_TOOLS.get(team, []))
        total = TEAM_SOFTWARE_MONTHLY[team]

        # Build the line items as shown in the dashboard hover (seat share as last line)
        line_items = list(direct)
        if seat_share > 0:
            seats = SEAT_COUNTS[team]
            line_items.append((f"Claude+Slack · {seats} seat{'s' if seats != 1 else ''}", seat_share))

        result.by_team[team] = TeamSoftwareDetail(
            team=team,
            seat_share=seat_share,
            direct_tools=line_items,
            total=total,
        )

    return result


def compute_software_with_xero(xero_actual: float) -> SoftwareResult:
    """Same as compute_software() but records the Xero 835 actual and residual."""
    result = compute_software()
    result.xero_actual = xero_actual
    # Key total + company buckets vs Xero actual
    key_total = result.team_total + result.company_total
    result.xero_residual = round(xero_actual - key_total, 2)
    return result
