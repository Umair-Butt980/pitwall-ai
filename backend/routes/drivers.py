from __future__ import annotations

from fastapi import APIRouter, Path

from models.race import DriverCircuitStats
from services import ergast_service

router = APIRouter(prefix="/api/drivers", tags=["drivers"])

# Ergast IDs are lowercase slugs — reject anything else before it reaches upstream.
_ID = Path(pattern=r"^[a-z0-9_]{1,50}$")


@router.get("/{driver_id}/stats/{circuit}", response_model=DriverCircuitStats)
async def driver_circuit_stats(driver_id: str = _ID, circuit: str = _ID) -> dict:
    """Aggregate a driver's record at a circuit (Ergast IDs, e.g. 'hamilton').

    Pulls every past finish, then rolls them up into the summary numbers the
    driver-performance agent and the UI need.
    """
    results = await ergast_service.get_driver_circuit_results(driver_id, circuit)

    starts = len(results)
    wins = sum(1 for r in results if r["position"] == 1)
    podiums = sum(1 for r in results if r["position"] <= 3)
    positions = [r["position"] for r in results]
    avg_finish = round(sum(positions) / starts, 2) if starts else None
    best_finish = min(positions) if positions else None

    return {
        "driver_id": driver_id,
        "circuit": circuit,
        "starts": starts,
        "wins": wins,
        "podiums": podiums,
        "avg_finish": avg_finish,
        "best_finish": best_finish,
        "results": results,
    }
