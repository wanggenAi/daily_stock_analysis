"""Read-only V4 investor summary for the existing stock website.

This endpoint does not authorize orders, control ChatGPT or fetch brokerage data.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.services.investor_v4_delivery import latest_report

router = APIRouter()


@router.get("/latest", summary="Get bounded dated investor V4 handoff")
def get_latest_v4_report() -> JSONResponse:
    report = latest_report()
    return JSONResponse(
        content=report,
        headers={"Cache-Control": "no-store, max-age=0"},
    )
