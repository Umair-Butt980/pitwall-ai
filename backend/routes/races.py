from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from models.race import CircuitWinner, Race
from services import ergast_service

router = APIRouter(prefix="/api/races", tags=["races"])


@router.get("", response_model=list[Race])
async def list_races(
    year: int = Query(default_factory=lambda: datetime.now().year),
) -> list[dict]:
    """Full race calendar for a season (defaults to the current year)."""
    return await ergast_service.get_season_schedule(year)


@router.get("/result")
async def race_result(year: int, round: int) -> dict | None:
    """Actual top-3 finishers of a past race — used to backtest predictions.

    Returns None if the race hasn't been run / results aren't published yet.
    """
    return await ergast_service.get_race_result(year, round)


@router.get("/{circuit_id}/history", response_model=list[CircuitWinner])
async def circuit_history(circuit_id: str) -> list[dict]:
    """Past race winners at a circuit (Ergast circuitId, e.g. 'monaco')."""
    return await ergast_service.get_circuit_results(circuit_id)
