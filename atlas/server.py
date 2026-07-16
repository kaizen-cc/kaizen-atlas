"""FastAPI dashboard server.

    uvicorn atlas.server:app --reload --port 8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from atlas.snapshot import load_latest, load_snapshot

app = FastAPI(title="Kaizen Atlas", docs_url=None, redoc_url=None)

DASHBOARD_HTML = Path(__file__).parent / "dashboard" / "index.html"


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    if not DASHBOARD_HTML.exists():
        raise HTTPException(status_code=404, detail="Dashboard HTML not found")
    return HTMLResponse(content=DASHBOARD_HTML.read_text(encoding="utf-8"))


@app.get("/api/snapshot")
def snapshot_latest() -> JSONResponse:
    data = load_latest()
    if data is None:
        raise HTTPException(
            status_code=503,
            detail="No snapshot available. Run: python scripts/refresh.py",
        )
    return JSONResponse(content=data)


@app.get("/api/snapshot/{year}/{month}")
def snapshot_by_month(year: int, month: int) -> JSONResponse:
    data = load_snapshot(year, month)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No snapshot for {year}-{month:02d}")
    return JSONResponse(content=data)
