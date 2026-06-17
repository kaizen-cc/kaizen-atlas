"""Pull finalized Stripe invoices for a given calendar month.

Stripe date filter must use a nested dict, not bracket-string syntax —
bracket syntax is silently ignored by the API (confirmed in HANDOFF).
"""

import calendar
import datetime
import stripe

from atlas.config import require


def _epoch(year: int, month: int, day: int) -> int:
    return int(datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc).timestamp())


def fetch_invoices(year: int, month: int) -> list[dict]:
    """Return all finalized invoices created in the given month, with line items expanded."""
    stripe.api_key = require("STRIPE_API_KEY")

    last_day = calendar.monthrange(year, month)[1]
    gte = _epoch(year, month, 1)
    lt = _epoch(year, month, last_day) + 86400  # exclusive upper bound: start of next day

    invoices = stripe.Invoice.list(
        created={"gte": gte, "lt": lt},
        expand=["data.lines"],
        limit=100,
        status="all",  # we filter by status in engine.py; fetch everything finalized
    ).auto_paging_iter()

    return [inv for inv in invoices if inv.get("status") in ("paid", "open", "uncollectible")]
