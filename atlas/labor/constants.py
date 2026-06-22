"""Roster constants for the labor engine.

Payment types:
  flat_monthly  — fixed cost per month regardless of hours logged.
                  Toggl hours are used only for per-client allocation ratios.
  hourly        — Toggl hours × Toggl labor_cost rate.

toggl_uid matches the uid field from the Toggl workspace_users API.
flat_amount is in USD/month; only set for flat_monthly workers.

Low-tracking threshold: salary workers who log fewer than this many hours
in a month get a flag in the LaborResult. Adjust as the team norm evolves.
"""

LOW_TRACKING_HOURS_THRESHOLD = 100  # hours/month

ROSTER: list[dict] = [
    # ── Meta ──────────────────────────────────────────────────────────────
    {"name": "Mark",    "team": "Meta",    "type": "flat_monthly", "flat_amount": 3500,  "toggl_uid": 8315976},
    {"name": "Dipesh",  "team": "Meta",    "type": "hourly",                             "toggl_uid": 11969919},
    {"name": "Thomas",  "team": "Meta",    "type": "hourly",                             "toggl_uid": 12692250},
    {"name": "Gustavo", "team": "Meta",    "type": "hourly",                             "toggl_uid": 13031136},
    {"name": "Eduarda", "team": "Meta",    "type": "hourly",                             "toggl_uid": 13197159},
    {"name": "Arthur",  "team": "Meta",    "type": "hourly",                             "toggl_uid": 13197158},
    {"name": "Priscila","team": "Meta",    "type": "hourly",                             "toggl_uid": 12899606},
    {"name": "Camille", "team": "Meta",    "type": "hourly",                             "toggl_uid": 12809307},
    # ── Creative ──────────────────────────────────────────────────────────
    {"name": "Nelson",  "team": "Creative","type": "hourly",                             "toggl_uid": 12119409},
    {"name": "Hillary", "team": "Creative","type": "hourly",                             "toggl_uid": 12167209},
    {"name": "Jazem",   "team": "Creative","type": "hourly",                             "toggl_uid": 11562598},
    {"name": "Teuta",   "team": "Creative","type": "hourly",                             "toggl_uid": 12583983},
    {"name": "Mira",    "team": "Creative","type": "hourly",                             "toggl_uid": 13071043},
    {"name": "Daniel",  "team": "Creative","type": "hourly",                             "toggl_uid": 13071044},
    # Photographers (Jonathan Quiroz, Tanner Walsh) paid per shoot via Xero 830 — Phase 3
    # ── Google ────────────────────────────────────────────────────────────
    {"name": "Sultan",  "team": "Google",  "type": "hourly",                             "toggl_uid": 12583882},
    {"name": "Aneesa",  "team": "Google",  "type": "hourly",                             "toggl_uid": 11562599},
    {"name": "Salman",  "team": "Google",  "type": "hourly",                             "toggl_uid": 12135755},
    # ── Social ────────────────────────────────────────────────────────────
    {"name": "Peter",   "team": "Social",  "type": "hourly",                             "toggl_uid": 12083718},
    {"name": "Camila",  "team": "Social",  "type": "hourly",                             "toggl_uid": 12187826},
    # ── Email ─────────────────────────────────────────────────────────────
    {"name": "Mel",     "team": "Email",   "type": "flat_monthly", "flat_amount": 4500,  "toggl_uid": 12083716},
    {"name": "Eunhye",  "team": "Email",   "type": "hourly",                             "toggl_uid": 11545886},
    {"name": "Adriana", "team": "Email",   "type": "hourly",                             "toggl_uid": 12331626},
    {"name": "Andres",  "team": "Email",   "type": "hourly",                             "toggl_uid": 11926482},
    {"name": "Dani",    "team": "Email",   "type": "hourly",                             "toggl_uid": 13020820},
    {"name": "Niro",    "team": "Email",   "type": "hourly",                             "toggl_uid": 13071045},
    {"name": "Facundo", "team": "Email",   "type": "hourly",                             "toggl_uid": 13095513},
    {"name": "Lawrence","team": "Email",   "type": "hourly",                             "toggl_uid": 13161600},
    {"name": "Renato",  "team": "Email",   "type": "hourly",                             "toggl_uid": 13161601},
    {"name": "Fernando","team": "Email",   "type": "hourly",                             "toggl_uid": 13178435},
    # ── Web ───────────────────────────────────────────────────────────────
    {"name": "Jesus",   "team": "Web",     "type": "flat_monthly", "flat_amount": 2500,  "toggl_uid": 12083717},
    {"name": "Lubin",   "team": "Web",     "type": "hourly",                             "toggl_uid": 12763731},
    {"name": "Andrew",  "team": "Web",     "type": "hourly",                             "toggl_uid": 11830763},
    {"name": "Francisco","team": "Web",    "type": "hourly",                             "toggl_uid": 12881547},
    {"name": "Andres G","team": "Web",     "type": "hourly",                             "toggl_uid": 12965016},
    # ── GHL ───────────────────────────────────────────────────────────────
    {"name": "Clare",   "team": "GHL",     "type": "hourly",                             "toggl_uid": 12741511},
    {"name": "Kennedy", "team": "GHL",     "type": "hourly",                             "toggl_uid": 13105213},
    # ── Operations (company overhead — not a delivery team) ───────────────
    {"name": "Fabi",    "team": "Operations","type": "flat_monthly","flat_amount": 2250, "toggl_uid": 12083719},
    {"name": "Jorgi",   "team": "Operations","type": "hourly",                           "toggl_uid": 8315481},  # Jorgi Conti
    {"name": "Santi",   "team": "Operations","type": "flat_monthly","flat_amount": 0,    "toggl_uid": 6406739},
]

# Workers removed from active rosters — present in Toggl but must not appear
# in labor computations or the employee tab.
EXCLUDED_TOGGL_UIDS: frozenset[int] = frozenset([
    12965017,  # Rafael
    # Waseem, Isaly, Angel, Del — add uids here if they surface in pulls
])

# Toggl workspace ID
TOGGL_WORKSPACE_ID = 5712162

# Delivery teams (excludes Operations)
DELIVERY_TEAMS: tuple[str, ...] = (
    "Meta", "Email", "Google", "Social", "Web", "Creative", "SEO", "GHL"
)
