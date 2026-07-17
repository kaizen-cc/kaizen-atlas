"""Snapshot builder and loader.

A snapshot is a dated JSON file under data/snapshots/ that bundles all
data needed by the dashboard for one month. The daily refresh job writes
one per run; the server reads the latest.
"""

from __future__ import annotations

import json
from calendar import month_abbr
from pathlib import Path

SNAPSHOTS_DIR = Path(__file__).parent.parent / "data" / "snapshots"

# Team display colours (match prototype)
TEAM_COLORS: dict[str, str] = {
    "Meta":     "#D93B47",
    "Email":    "#F2F2F2",
    "Google":   "#E8857F",
    "Social":   "#9A9AA2",
    "Web":      "#A82430",
    "Creative": "#CC6666",
    "SEO":      "#6E6E76",
    "GHL":      "#5A5A60",
}

# Off-Stripe clients (shown with check/ACH badge)
OFF_STRIPE_CLIENTS = frozenset(["Tejas Brewery", "Giant Texas", "Tejas Beer", "Oceanbox"])

# Static rate strings for the Employees tab (display only)
RATE_DISPLAY: dict[str, str] = {
    "Mark":      "$3,500 / mo",
    "Dipesh":    "$4,000 / mo",
    "Thomas":    "$15 / hr",
    "Gustavo":   "$12→$15 / hr",
    "Eduarda":   "$15 / hr",
    "Arthur":    "$15 / hr",
    "Priscila":  "$10 / hr",
    "Camille":   "$6 / hr",
    "Nelson":    "$15 / hr",
    "Hillary":   "$12 / hr",
    "Jazem":     "$15.50 / hr",
    "Teuta":     "$25 / hr",
    "Mira":      "$12→$15 / hr",
    "Daniel":    "$10→$12 / hr",
    "Sultan":    "$15 / hr",
    "Aneesa":    "$8 / hr",
    "Salman":    "$10 / hr",
    "Peter":     "$19 / hr",
    "Camila":    "$15 / hr",
    "Mel":       "$4,500 / mo",
    "Eunhye":    "$25 / hr",
    "Adriana":   "$15 / hr",
    "Andres":    "$6.50 / hr",
    "Dani":      "$15 / hr",
    "Niro":      "$10→$12 / hr",
    "Facundo":   "$12→$15 / hr",
    "Lawrence":  "$10→$12 / hr",
    "Renato":    "$10→$12 / hr",
    "Fernando":  "$19 / hr",
    "Jesus":     "$2,500 / mo",
    "Lubin":     "$20 / hr",
    "Andrew":    "$10 / hr",
    "Francisco": "$15 / hr",
    "Andres G":  "$10 / hr",
    "Clare":     "$25 / hr",
    "Kennedy":   "$10→$12 / hr",
    "Fabi":      "$2,250 / mo",
    "Jorgi":     "$13.50 / hr",
    "Santi":     "—",
}


def build_snapshot(
    year: int,
    month: int,
    margin_result,
    revenue_result,
    software_result,
    prior_snapshot: dict | None = None,
    xero_pnl_current: dict | None = None,
    xero_pnl_prior: dict | None = None,
    xero_actuals: dict | None = None,
    generated_at: str = "",
) -> dict:
    """Assemble the full dashboard snapshot from engine outputs."""
    from atlas.labor.constants import ROSTER
    from atlas.software.constants import DIRECT_TOOLS, SEAT_COUNTS, SEAT_SHARE_ACTUAL

    month_label = f"{_month_name(month)} {year}"

    # ── Company ──────────────────────────────────────────────────────────────
    co = margin_result.company
    mrr_total = revenue_result.mrr_total
    oneoff_total = revenue_result.oneoff_total
    total_rev = co.total_revenue
    mrr_pct = round(mrr_total / total_rev * 100, 1) if total_rev else 0.0
    oneoff_pct = round(100 - mrr_pct, 1)

    # ── Override with Xero actuals when available ─────────────────────────────
    xero_revenue = xero_actuals.get("total_income") if xero_actuals else None
    xero_net     = xero_actuals.get("net_profit")   if xero_actuals else None

    actual_revenue = xero_revenue if xero_revenue else total_rev
    actual_profit  = xero_net     if xero_net is not None else co.net_profit
    actual_margin  = round(actual_profit / actual_revenue * 100, 1) if actual_revenue else co.margin_pct

    xero_total = actual_revenue
    residual = round(xero_total - revenue_result.mrr_total - revenue_result.oneoff_total, 2)

    company = {
        "revenue": round(actual_revenue, 2),
        "mrr_total": round(mrr_total, 2),
        "oneoff_total": round(oneoff_total, 2),
        "net_profit": round(actual_profit, 2),
        "margin_pct": actual_margin,
        "mrr_pct": mrr_pct,
        "oneoff_pct": oneoff_pct,
        "stripe_recognized": round(revenue_result.mrr_total + revenue_result.oneoff_total, 2),
        "xero_total": round(xero_total, 2),
        "residual": residual,
        "subscriber_count": None,  # needs Stripe subscription count
    }

    # ── Prior month ───────────────────────────────────────────────────────────
    prior: dict = {}
    if prior_snapshot:
        pc = prior_snapshot.get("company", {})
        prior = {
            "revenue": pc.get("revenue"),
            "net_profit": pc.get("net_profit"),
            "margin_pct": pc.get("margin_pct"),
            "mrr_total": pc.get("mrr_total"),
            # Team lookup: {team_name: {mrr, oneoff, lab, sw}}
            "teams": {t["n"]: t for t in prior_snapshot.get("teams", [])},
            # Client lookup: {client_name: {rev, cost, mpct}}
            "clients": {c["n"]: c for c in prior_snapshot.get("clients", [])},
        }
    elif xero_pnl_current and xero_pnl_current.get("comparison_pnl"):
        cp = xero_pnl_current["comparison_pnl"]
        prior = {
            "revenue": float(cp.get("total_income", 0)),
            "net_profit": None,
            "margin_pct": None,
            "mrr_total": None,
            "teams": {},
            "clients": {},
        }

    # ── Teams ─────────────────────────────────────────────────────────────────
    team_members: dict[str, list[str]] = {}
    for m in ROSTER:
        team_members.setdefault(m["team"], []).append(m["name"])

    teams = []
    for tm in margin_result.by_team.values():
        t = tm.team
        color = TEAM_COLORS.get(t, "#67676F")

        # Software breakdown lines
        sw_break = []
        for name, amt in DIRECT_TOOLS.get(t, []):
            sw_break.append([name, amt])
        seat_share = SEAT_SHARE_ACTUAL.get(t, 0.0)
        if seat_share > 0:
            seats = SEAT_COUNTS.get(t, 0)
            sw_break.append([f"Claude + Slack · {seats} seat{'s' if seats != 1 else ''}", seat_share])

        # Top 5 clients for this team by MRR
        team_cust = revenue_result.revenue_by_team_customer.get(t, {})
        top_clients = sorted(team_cust.items(), key=lambda x: -x[1])[:5]

        teams.append({
            "n": t,
            "c": color,
            "mrr": tm.mrr,
            "oneoff": tm.oneoff,
            "lab": tm.labor if tm.labor > 0 else None,
            "sw": tm.software,
            "sw_break": sw_break,
            "emp": team_members.get(t, []),
            "top_clients": [[n, round(v, 2)] for n, v in top_clients],
        })

    # ── Clients ───────────────────────────────────────────────────────────────
    clients = []
    for cm in margin_result.by_client.values():
        if cm.revenue <= 0 and cm.labor_cost <= 0:
            continue
        clients.append({
            "n": cm.name,
            "rev": cm.revenue,
            "cost": cm.labor_cost,
            "margin": cm.margin,
            "mpct": cm.margin_pct,
            "agency": cm.agency,
            "off_stripe": cm.name in OFF_STRIPE_CLIENTS,
        })

    # ── Roster ────────────────────────────────────────────────────────────────
    roster = []
    for m in ROSTER:
        if m["name"] == "Santi":
            continue  # owner, not shown in employee tab
        pay_type = m["type"]  # flat_monthly → salary display
        display_type = "salary" if pay_type == "flat_monthly" else "hourly"
        roster.append({
            "team": m["team"],
            "name": m["name"],
            "rate": RATE_DISPLAY.get(m["name"], "—"),
            "type": display_type,
        })
    # Photographers are contractors, add manually
    roster.extend([
        {"team": "Creative", "name": "Jonathan Quiroz (photo)", "rate": "per shoot · Xero", "type": "contractor"},
        {"team": "Creative", "name": "Tanner Walsh (photo)",    "rate": "per shoot · Xero", "type": "contractor"},
    ])

    # ── Monthly history ───────────────────────────────────────────────────────
    monthly: list[list] = []
    if prior_snapshot:
        monthly = prior_snapshot.get("monthly", [])
    # Append current month if not already in list
    cur_abbr = month_abbr[month]
    if not any(m[0] == cur_abbr for m in monthly):
        monthly.append([cur_abbr, round(total_rev, 2)])
    else:
        # Update in place
        monthly = [[m[0], round(total_rev, 2)] if m[0] == cur_abbr else m for m in monthly]

    # ── Xero cost increases ───────────────────────────────────────────────────
    xero_incr = _build_xero_incr(xero_pnl_current, xero_pnl_prior)

    return {
        "meta": {
            "year": year,
            "month": month,
            "month_label": month_label,
            "generated_at": generated_at,
            "total_labor": round(margin_result.company.total_labor, 2),
            "total_software": round(margin_result.company.total_software, 2),
        },
        "company": company,
        "prior": prior,
        "teams": teams,
        "clients": clients,
        "roster": roster,
        "monthly": monthly,
        "xero_incr": xero_incr,
        "low_tracking_flags": margin_result.low_tracking_flags,
    }


def _build_xero_incr(current_pnl: dict | None, prior_pnl: dict | None) -> list[dict]:
    """Build cost-increase list from raw Xero REST ProfitAndLoss responses."""
    if not current_pnl or not prior_pnl:
        return []

    EXCLUDE = frozenset([
        "Stripe Income", "Services", "Owners Draw",
        "AMEX", "BofA", "Stripe USD", "PayPal", "Gusto Clearing",
        "Total Revenue", "Total Cost of Sales", "Total Operating Expenses", "Net Income",
    ])

    COST_SECTIONS = frozenset(["less cost of sales", "operating expenses", "cost of sales"])

    def _extract_accounts(pnl: dict) -> dict[str, float]:
        """Extract account name → amount from raw Xero Rows for cost sections only."""
        out: dict[str, float] = {}
        try:
            rows = pnl["Reports"][0]["Rows"]
        except (KeyError, IndexError):
            return out

        in_cost_section = False
        for section in rows:
            title = section.get("Title", "").lower()
            in_cost_section = any(cs in title for cs in COST_SECTIONS)
            if not in_cost_section:
                continue
            for row in section.get("Rows", []):
                if row.get("RowType") in ("SummaryRow",):
                    continue
                cells = row.get("Cells", [])
                if len(cells) < 2:
                    continue
                name = (cells[0].get("Value") or "").strip()
                if not name or name in EXCLUDE:
                    continue
                try:
                    val = float(str(cells[1].get("Value") or "0").replace(",", ""))
                    if val != 0:
                        out[name] = val
                except ValueError:
                    pass
        return out

    cur = _extract_accounts(current_pnl)
    prior = _extract_accounts(prior_pnl)

    increases = []
    for name, cur_amt in cur.items():
        pri_amt = prior.get(name, 0.0)
        incr = cur_amt - pri_amt
        if incr > 50:  # ignore noise below $50
            increases.append({
                "cat": name,
                "prior": round(pri_amt, 2),
                "current": round(cur_amt, 2),
                "incr": round(incr, 2),
            })

    increases.sort(key=lambda x: -x["incr"])
    return increases[:5]


def save_snapshot(snapshot: dict) -> Path:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    y = snapshot["meta"]["year"]
    m = snapshot["meta"]["month"]
    path = SNAPSHOTS_DIR / f"{y}-{m:02d}.json"
    path.write_text(json.dumps(snapshot, indent=2))
    return path


def load_latest() -> dict | None:
    if not SNAPSHOTS_DIR.exists():
        return None
    files = sorted(SNAPSHOTS_DIR.glob("*.json"), reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text())


def load_snapshot(year: int, month: int) -> dict | None:
    path = SNAPSHOTS_DIR / f"{year}-{month:02d}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _month_name(month: int) -> str:
    return [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ][month - 1]
