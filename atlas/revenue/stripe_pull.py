"""Pull finalized Stripe invoices relevant to a given calendar month.

MRR invoices are created in the prior month (billed in advance for the coming
period). Fetching only the target month by `created` date would return
next-month period lines, not the current month's MRR. We therefore fetch a
two-month window (M-1 through end of M) and let the engine filter MRR by
subscription period month and one-off by invoice created month.

Stripe date filter must use a nested dict, not bracket-string syntax —
bracket syntax is silently ignored by the API (confirmed in HANDOFF).
"""

import calendar
import datetime
import stripe

from atlas.config import require


def _epoch(year: int, month: int, day: int) -> int:
    return int(datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc).timestamp())


def _prior_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def fetch_invoices(year: int, month: int) -> list[dict]:
    """Return all finalized invoices relevant to the given month, with line items expanded.

    Fetches a two-month window (M-1 through end of M) so that subscription
    invoices created in the prior month (but covering the target period) are
    included. The engine filters MRR by period month and one-off by invoice
    created month.
    """
    stripe.api_key = require("STRIPE_API_KEY")

    prior_year, prior_month = _prior_month(year, month)
    gte = _epoch(prior_year, prior_month, 1)

    last_day = calendar.monthrange(year, month)[1]
    lt = _epoch(year, month, last_day) + 86400  # exclusive: start of day after last day

    invoices = stripe.Invoice.list(
        created={"gte": gte, "lt": lt},
        expand=["data.lines"],
        limit=100,
    ).auto_paging_iter()

    return [inv for inv in invoices if inv.get("status") in ("paid", "open", "uncollectible")]
