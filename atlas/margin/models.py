"""Data models for the margin engine."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TeamMargin:
    team: str
    mrr: float
    oneoff: float
    labor: float
    software: float

    @property
    def revenue(self) -> float:
        return self.mrr + self.oneoff

    @property
    def contribution_margin(self) -> float:
        return self.revenue - self.labor - self.software

    @property
    def contribution_pct(self) -> float:
        return round(self.contribution_margin / self.revenue * 100, 1) if self.revenue else 0.0


@dataclass
class ClientMargin:
    name: str
    agency: str | None  # None for direct clients
    revenue: float
    labor_cost: float

    @property
    def margin(self) -> float:
        return self.revenue - self.labor_cost

    @property
    def margin_pct(self) -> float:
        return round(self.margin / self.revenue * 100, 1) if self.revenue else 0.0


@dataclass
class CompanyPL:
    year: int
    month: int
    total_revenue: float
    total_labor: float
    total_software: float   # team + company-level buckets

    @property
    def net_profit(self) -> float:
        return round(self.total_revenue - self.total_labor - self.total_software, 2)

    @property
    def margin_pct(self) -> float:
        if not self.total_revenue:
            return 0.0
        return round(self.net_profit / self.total_revenue * 100, 1)


@dataclass
class MarginResult:
    company: CompanyPL
    by_team: dict[str, TeamMargin] = field(default_factory=dict)
    # Keyed by Toggl client name (end-client level, white-label resolved)
    by_client: dict[str, ClientMargin] = field(default_factory=dict)
    low_tracking_flags: list[str] = field(default_factory=list)
    unmatched_revenue_lines: list[dict] = field(default_factory=list)
