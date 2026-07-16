"""White-label agency mapping for per-client margin attribution.

Keys are exact Toggl client names (end clients that workers track time against).
Values are the Stripe customer names (the agency, who pays Kaizen).

IMPORTANT: Stripe customer names must match exactly what appears in Stripe.
"RECA" in the user shorthand = "RE Creative Agency" in Stripe — verify all
agency names against Stripe before relying on revenue_by_client figures.
"""

from __future__ import annotations
from collections import defaultdict


# toggl_client_name → stripe_customer_name
WHITE_LABEL_MAP: dict[str, str] = {
    # RE Creative Agency
    "Brooklyn Water Bagel":   "RE Creative Agency",
    "dos":                    "RE Creative Agency",
    "House of GRO":           "RE Creative Agency",
    "Pegasus Food Group":     "RE Creative Agency",
    "Propr Dental":           "RE Creative Agency",
    "Raising The Bar":        "RE Creative Agency",
    # Blue Cherry Group
    "Brooklyn Kayak Co":      "Blue Cherry Group",
    "Select Home Warranty":   "Blue Cherry Group",
    "Slendid":                "Blue Cherry Group",
    "We Got Nuts":            "Blue Cherry Group",
    # Lux Marketing Company
    "21 Property Group":      "Lux Marketing Company",
    "Alpha Enterprises":      "Lux Marketing Company",
    "Bascom's Chop House":    "Lux Marketing Company",
    "Crown Rally":            "Lux Marketing Company",
    "Cypress Chiropractic":   "Lux Marketing Company",
    "Freedom Repair":         "Lux Marketing Company",
    "Motiv Society":          "Lux Marketing Company",
    "Tampa Auto Gallery":     "Lux Marketing Company",
    "Thalio Funding":         "Lux Marketing Company",
    "Vivo Now":               "Lux Marketing Company",
    # So Shall We
    "Brainista":              "So Shall We",
    "Momentum":               "So Shall We",
    "NxGen Candles":          "So Shall We",
    # ZenChange Marketing
    "Alelaluna":              "ZenChange Marketing",
    # We Think Big
    "Four Star Homes":        "We Think Big",
}

# Reverse map: stripe_customer_name → [toggl_client_names]
AGENCY_TO_CLIENTS: dict[str, list[str]] = defaultdict(list)
for _client, _agency in WHITE_LABEL_MAP.items():
    AGENCY_TO_CLIENTS[_agency].append(_client)
AGENCY_TO_CLIENTS = dict(AGENCY_TO_CLIENTS)

# All Stripe customer names that are agencies (not end clients)
AGENCY_CUSTOMERS: frozenset[str] = frozenset(WHITE_LABEL_MAP.values())
