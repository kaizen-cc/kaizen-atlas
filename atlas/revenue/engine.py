"""Revenue engine: Phase 1.

Orchestrates the Stripe pull, applies the off-Stripe rescue list, deduplicates
by invoice ID, splits MRR (subscription line items, bucketed by subscription
period month) from one-off (manual invoice items), excludes Ad Spend
Reimbursement pass-through, normalizes descriptions, and maps to teams.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from .classifier import is_pass_through, map_to_team
from .constants import OFF_STRIPE_RESCUE
from .stripe_pull import fetch_invoices


@dataclass
class RevenueResult:
    year: int
    month: int
    # MRR by team in dollars, bucketed by subscription period month
    mrr_by_team: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    # One-off by team in dollars
    oneoff_by_team: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    # Lines that didn't match any team (billing-hygiene visibility)
    unmatched_lines: list[dict] = field(default_factory=list)

    @property
    def oneoff_total(self) -> float:
        return sum(self.oneoff_by_team.values())

    @property
    def mrr_total(self) -> float:
        return sum(self.mrr_by_team.values())


def _customer_name(invoice: dict) -> str:
    # customer_name is a top-level field on the invoice object
    return (invoice.get("customer_name") or "").strip()


def _is_eligible(invoice: dict) -> bool:
    """An invoice counts as revenue if Stripe marks it paid OR the customer
    is on the off-Stripe rescue list."""
    if invoice.get("status") == "paid":
        return True
    return _customer_name(invoice) in OFF_STRIPE_RESCUE


def _subscription_period_month(line: dict) -> tuple[int, int] | None:
    """Return (year, month) from a subscription line item's period.

    The period start determines which month the MRR belongs to, regardless
    of when the invoice was created or paid. This neutralizes late and
    multi-month catch-up checks.
    """
    period = line.get("period")
    if not period or not period.get("start"):
        return None
    dt = datetime.datetime.fromtimestamp(period["start"], tz=datetime.timezone.utc)
    return dt.year, dt.month


def _line_type(line: dict) -> str:
    """'subscription' or 'oneoff' based on the line item parent type."""
    parent = line.get("parent") or {}
    if parent.get("type") == "subscription_item_details":
        return "subscription"
    return "oneoff"


def compute_revenue(year: int, month: int) -> RevenueResult:
    result = RevenueResult(year=year, month=month)
    seen_invoice_ids: set[str] = set()

    invoices = fetch_invoices(year, month)

    for inv in invoices:
        inv_id = inv.get("id", "")

        # Dedup by invoice ID (rescue-list clients that are also marked paid
        # in Stripe must not be counted twice)
        if inv_id in seen_invoice_ids:
            continue

        if not _is_eligible(inv):
            continue

        seen_invoice_ids.add(inv_id)

        lines_data = inv.get("lines") or {}
        lines = lines_data.get("data") if isinstance(lines_data, dict) else []
        if not lines:
            continue

        for line in lines:
            amount_cents = line.get("amount", 0)
            if amount_cents <= 0:
                continue  # credits and zero lines carry no revenue

            description = line.get("description") or ""

            if is_pass_through(description):
                continue

            team = map_to_team(description)
            amount_dollars = amount_cents / 100.0

            if _line_type(line) == "subscription":
                period_ym = _subscription_period_month(line)
                # Only count MRR that belongs to this calendar month
                if period_ym and period_ym == (year, month):
                    result.mrr_by_team[team] += amount_dollars
            else:
                result.oneoff_by_team[team] += amount_dollars

            if team == "Other":
                result.unmatched_lines.append(
                    {
                        "invoice_id": inv_id,
                        "customer": _customer_name(inv),
                        "description": description,
                        "amount": amount_dollars,
                    }
                )

    return result
