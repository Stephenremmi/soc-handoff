"""Serve the signed-in dashboard and the local liveness probe."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..auth.analyst import Analyst

router = APIRouter()


@router.get("/", include_in_schema=False)
def page(_actor: Analyst):
    index = Path(__file__).resolve().parents[1] / "web" / "index.html"
    return FileResponse(index, headers={"Cache-Control": "no-store"})


@router.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
