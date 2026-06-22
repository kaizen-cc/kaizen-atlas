"""Pull labor data from Toggl Reports API v3.

Auth: HTTP Basic with api_token:api_token.
All calls are read-only.
"""

from __future__ import annotations

import base64
import calendar
import urllib.request
import urllib.error
import json

from atlas.config import require
from atlas.labor.constants import TOGGL_WORKSPACE_ID


def _auth_header() -> str:
    token = require("TOGGL_API_TOKEN")
    creds = base64.b64encode(f"{token}:api_token".encode()).decode()
    return f"Basic {creds}"


def _get(path: str) -> dict | list:
    url = f"https://api.track.toggl.com{path}"
    req = urllib.request.Request(url, headers={"Authorization": _auth_header()})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _post(path: str, body: dict) -> dict | list:
    url = f"https://api.track.toggl.com{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_workspace_users() -> dict[int, dict]:
    """Return uid → {name, email, labor_cost} for all active workspace members."""
    wid = TOGGL_WORKSPACE_ID
    data = _get(f"/api/v9/workspaces/{wid}/workspace_users?page_size=200")
    return {
        u["uid"]: {
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "labor_cost": u.get("labor_cost"),  # $/hr; None if not set
        }
        for u in data
        if not u.get("inactive", False)
    }


def fetch_projects() -> dict[int, str]:
    """Return project_id → project_name for all active projects.

    Used to map Toggl project IDs to client names in per-client allocation.
    Fetches in pages of 200 until exhausted.
    """
    wid = TOGGL_WORKSPACE_ID
    projects: dict[int, str] = {}
    page = 1
    while True:
        data = _get(f"/api/v9/workspaces/{wid}/projects?active=true&page={page}&per_page=200")
        if not data:
            break
        for p in data:
            projects[p["id"]] = p["name"]
        if len(data) < 200:
            break
        page += 1
    return projects


def fetch_user_hours(year: int, month: int) -> list[dict]:
    """Return per-user per-project hour data for the given month.

    Returns a list of:
      {
        uid: int,
        project_id: int | None,
        seconds: int,
      }
    """
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day:02d}"

    wid = TOGGL_WORKSPACE_ID
    body = {
        "start_date": start,
        "end_date": end,
        "grouping": "users",
        "sub_grouping": "projects",
    }

    raw = _post(f"/reports/api/v3/workspace/{wid}/summary/time_entries", body)
    rows: list[dict] = []
    for group in raw.get("groups", []):
        uid = group["id"]
        for sub in group.get("sub_groups", []):
            rows.append({
                "uid": uid,
                "project_id": sub.get("id"),
                "seconds": sub.get("seconds", 0),
            })
    return rows
