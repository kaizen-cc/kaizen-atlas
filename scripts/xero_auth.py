#!/usr/bin/env python3
"""
One-time Xero OAuth2 setup script.

Run this once to get your XERO_TENANT_ID and XERO_REFRESH_TOKEN, then
paste them into your .env file. Never needs to be run again — the main
refresh script uses the refresh token to get new access tokens automatically.

Usage:
    python scripts/xero_auth.py
"""

import base64
import json
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from atlas.config import require

CLIENT_ID     = require("XERO_CLIENT_ID")
CLIENT_SECRET = require("XERO_CLIENT_SECRET")
REDIRECT_URI  = "http://localhost:8765/callback"
SCOPE         = "openid profile email offline_access accounting.reports.profitandloss.read accounting.banktransactions.read"
TENANT_ID     = "b9117e1e-edbe-4e3e-ab55-6122799ec279"  # K Barry Inc / Kaizen Marketing

AUTH_URL = (
    "https://login.xero.com/identity/connect/authorize"
    f"?response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPE)}"
)

TOKEN_URL       = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"

_code_received = threading.Event()
_auth_code     = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Authorized! You can close this tab and return to the terminal.</h2>")
        _code_received.set()

    def log_message(self, *_):
        pass  # suppress server logs


def _exchange_code(code: str) -> dict:
    credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _get_tenant_id(access_token: str) -> str:
    req = urllib.request.Request(
        CONNECTIONS_URL,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        connections = json.loads(r.read())
    if not connections:
        raise RuntimeError("No Xero organisations found for this account.")
    if len(connections) > 1:
        print("\nMultiple Xero organisations found:")
        for i, c in enumerate(connections):
            print(f"  [{i}] {c['tenantName']} ({c['tenantId']})")
        idx = int(input("Enter the number for K Barry Inc: ").strip())
        return connections[idx]["tenantId"]
    return connections[0]["tenantId"]


def main():
    print("Starting local callback server on port 8765...")
    server = HTTPServer(("localhost", 8765), _CallbackHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    print(f"\nOpen this URL in your browser to authorize:\n")
    print(f"  {AUTH_URL}\n")
    try:
        webbrowser.open(AUTH_URL)
    except Exception:
        pass

    print("Waiting for you to authorize in the browser...")
    _code_received.wait(timeout=120)
    server.shutdown()

    if not _auth_code:
        print("ERROR: No authorization code received. Did you authorize in the browser?")
        sys.exit(1)

    print("Authorization code received. Exchanging for tokens...")
    tokens = _exchange_code(_auth_code)
    refresh_token = tokens.get("refresh_token")
    access_token  = tokens.get("access_token")

    if not refresh_token:
        print("ERROR: No refresh token in response:", tokens)
        sys.exit(1)

    tenant_id = TENANT_ID

    print("\n" + "=" * 60)
    print("SUCCESS — add these two lines to your .env file:")
    print("=" * 60)
    print(f"XERO_TENANT_ID={tenant_id}")
    print(f"XERO_REFRESH_TOKEN={refresh_token}")
    print("=" * 60)


if __name__ == "__main__":
    main()
