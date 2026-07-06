from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from services import ergast_service

router = APIRouter(prefix="/api/standings", tags=["standings"])

# These proxy Jolpica through our Redis cache so every browser doesn't hit the
# (rate-limited) public API directly — one upstream call serves all visitors.

_YEAR = Query(default_factory=lambda: datetime.now().year, ge=1950, le=2100)


@router.get("/drivers")
async def driver_standings(year: int = _YEAR) -> list[dict]:
    """Current driver championship standings (cached, 6h TTL)."""
    return await ergast_service.get_driver_standings(year)


@router.get("/constructors")
async def constructor_standings(year: int = _YEAR) -> list[dict]:
    """Current constructor championship standings (cached, 6h TTL)."""
    return await ergast_service.get_constructor_standings(year)
