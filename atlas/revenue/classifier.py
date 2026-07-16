import re
from .constants import SERVICE_TO_TEAM, PASS_THROUGH_DESCRIPTION

# Matches leading quantity prefix: "3 x ", "1 x ", "1 • " (Stripe uses U+2022 bullet as separator)
_QTY_PREFIX = re.compile(r"^\d+\s*[xX•×]\s*")

# Matches trailing period-price suffix: " (at $750.00 / month)" etc.
_PERIOD_SUFFIX = re.compile(r"\s*\(at \$[\d,]+\.?\d*\s*/\s*\w+\)\s*$")


def normalize(description: str) -> str:
    s = _QTY_PREFIX.sub("", description.strip())
    s = _PERIOD_SUFFIX.sub("", s).strip()
    return s


def is_pass_through(description: str) -> bool:
    return normalize(description) == PASS_THROUGH_DESCRIPTION


def map_to_team(description: str) -> str:
    """Return the team name for a normalized line description.

    Returns "Other" for unrecognized lines so they surface in output
    rather than being silently dropped.
    """
    key = normalize(description)
    return SERVICE_TO_TEAM.get(key, "Other")
