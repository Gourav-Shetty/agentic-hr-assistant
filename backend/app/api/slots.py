"""Slots API: GET /api/slots -> the 3 bookable review slots."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.app.tools.booking import SLOTS

router = APIRouter(prefix="/api", tags=["slots"])


@router.get("/slots")
async def list_slots():
    try:
        return {"slots": list(SLOTS)}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})
