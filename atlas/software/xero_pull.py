"""Xero pull module: account 835 (Softwares) and 830 (Contractors).

Xero uses OAuth2. Required env vars:
  XERO_CLIENT_ID
  XERO_CLIENT_SECRET
  XERO_TENANT_ID
  XERO_REFRESH_TOKEN   — long-lived token; engine refreshes access token on each run

This module is a ready skeleton. Wire in credentials to activate.

Cash basis. Spend = negative of the Gross field on each transaction line.
Group by "Related account" (the vendor/payee) to match the allocation key.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from datetime import date

from atlas.config import get, require

XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_API_BASE = "https://api.xero.com/api.xro/2.0"

# Accounts we pull
ACCOUNT_835_CODE = "835"   # Softwares
ACCOUNT_830_CODE = "830"   # Contractors (offshore team + photographers)

# Accounts excluded from the cost-increase widget (clearing, income, payroll journals)
COST_WIDGET_EXCLUDE_KEYWORDS = frozenset([
    "AMEX", "BofA", "Stripe USD", "PayPal", "Gusto Clearing",
    "Stripe Income", "Services", "Owners Draw",
])


def _is_available() -> bool:
    """Return True if all required Xero env vars are set."""
    return all(
        get(v) for v in ("XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "XERO_TENANT_ID", "XERO_REFRESH_TOKEN")
    )


def _refresh_access_token() -> str:
    client_id = require("XERO_CLIENT_ID")
    client_secret = require("XERO_CLIENT_SECRET")
    refresh_token = require("XERO_REFRESH_TOKEN")

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(XERO_TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())

    # Xero refresh tokens are single-use — persist the new one immediately
    new_refresh = tokens.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        _update_env_refresh_token(new_refresh)

    return tokens["access_token"]


def _update_env_refresh_token(new_token: str) -> None:
    """Rewrite XERO_REFRESH_TOKEN in the .env file."""
    from pathlib import Path
    env_path = Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = []
    for line in lines:
        if line.startswith("XERO_REFRESH_TOKEN="):
            updated.append(f"XERO_REFRESH_TOKEN={new_token}")
        else:
            updated.append(line)
    env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _get_account_transactions(
    account_code: str,
    from_date: date,
    to_date: date,
    access_token: str,
) -> list[dict]:
    """Fetch cash-basis account transactions for the given account and date range."""
    tenant_id = require("XERO_TENANT_ID")
    params = urllib.parse.urlencode({
        "fromDate": from_date.isoformat(),
        "toDate": to_date.isoformat(),
        "ReportType": "CashBasis",
    })
    url = f"{XERO_API_BASE}/Reports/AccountTransactions?{params}&Code={account_code}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Xero-tenant-id": tenant_id,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_software_spend(year: int, month: int) -> dict[str, float] | None:
    """Return {vendor: amount} for Xero account 835 in the given month.

    Returns None if Xero credentials are not configured.
    Spend = negative of Gross (cash basis, outflows are negative).
    """
    if not _is_available():
        return None

    import calendar
    from datetime import date as _date
    last_day = calendar.monthrange(year, month)[1]
    from_date = _date(year, month, 1)
    to_date = _date(year, month, last_day)

    token = _refresh_access_token()
    raw = _get_account_transactions(ACCOUNT_835_CODE, from_date, to_date, token)

    spend: dict[str, float] = {}
    for txn in _parse_transactions(raw):
        vendor = txn.get("related_account", "Unknown")
        gross = txn.get("gross", 0.0)
        # Outflows are negative; flip sign to get positive spend
        if gross < 0:
            spend[vendor] = spend.get(vendor, 0.0) + abs(gross)

    return spend


def fetch_contractor_payments(year: int, month: int) -> dict[str, float] | None:
    """Return {contractor_name: amount} for Xero account 830 in the given month.

    Used to get photographer payments (Quiroz, Walsh) and reconcile against
    the offshore labor total to avoid double-counting with Gusto.
    Returns None if Xero credentials are not configured.
    """
    if not _is_available():
        return None

    import calendar
    from datetime import date as _date
    last_day = calendar.monthrange(year, month)[1]
    token = _refresh_access_token()
    raw = _get_account_transactions(
        ACCOUNT_830_CODE,
        _date(year, month, 1),
        _date(year, month, last_day),
        token,
    )

    payments: dict[str, float] = {}
    for txn in _parse_transactions(raw):
        name = txn.get("related_account", "Unknown")
        gross = txn.get("gross", 0.0)
        if gross < 0:
            payments[name] = payments.get(name, 0.0) + abs(gross)

    return payments


def fetch_cost_increases(
    year: int, month: int
) -> list[dict] | None:
    """Return the biggest cost increases vs the prior month across all Xero accounts.

    Excludes clearing accounts, income accounts, and payroll journal lines.
    Returns None if Xero credentials are not configured.
    Format: [{cat, prior_amount, current_amount, increase}]
    """
    if not _is_available():
        return None
    # Stub: full implementation in Phase 5 dashboard wiring
    raise NotImplementedError("fetch_cost_increases: implement in Phase 5")


def _parse_transactions(raw: dict) -> list[dict]:
    """Extract a flat list of transaction lines from the Xero AccountTransactions response."""
    rows = []
    for report in raw.get("Reports", []):
        for row in report.get("Rows", []):
            if row.get("RowType") == "Row":
                cells = row.get("Cells", [])
                # Column order: Date, Description, Reference, Debit, Credit, Gross, Related Account
                if len(cells) >= 7:
                    rows.append({
                        "date": cells[0].get("Value"),
                        "description": cells[1].get("Value"),
                        "gross": _parse_amount(cells[5].get("Value")),
                        "related_account": cells[6].get("Value"),
                    })
    return rows


def _parse_amount(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0
