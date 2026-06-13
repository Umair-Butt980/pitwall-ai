from __future__ import annotations

from typing import Any

from services.base import BaseHTTPService
from services.cache import cached

# Past results never change; the season schedule changes rarely.
_DAY = 24 * 60 * 60
_WEEK = 7 * _DAY


class ErgastService(BaseHTTPService):
    """Historical F1 data from the Jolpica API (the maintained Ergast successor).

    Jolpica mirrors the old Ergast schema, so every path ends in ".json" and
    responses are wrapped in an "MRData" envelope that we unwrap here — routes
    get clean lists, not the raw nesting.
    """

    base_url = "https://api.jolpi.ca/ergast/f1"

    @cached(prefix="ergast:schedule", ttl=_DAY)
    async def get_season_schedule(self, year: int) -> list[dict[str, Any]]:
        """All races for a season, flattened to the fields we store/show."""
        data = await self._get(f"/{year}.json")
        races = data["MRData"]["RaceTable"]["Races"]
        return [
            {
                "name": r["raceName"],
                "circuit": r["Circuit"]["circuitName"],
                "circuit_id": r["Circuit"]["circuitId"],
                "location": r["Circuit"]["Location"]["locality"],
                "country": r["Circuit"]["Location"]["country"],
                "lat": r["Circuit"]["Location"].get("lat"),
                "lon": r["Circuit"]["Location"].get("long"),
                "date": r["date"],
                "round": int(r["round"]),
                "year": int(r["season"]),
            }
            for r in races
        ]

    @cached(prefix="ergast:circuit_results", ttl=_WEEK)
    async def get_circuit_results(
        self, circuit_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Recent race winners/podiums at a circuit (across seasons)."""
        data = await self._get(
            f"/circuits/{circuit_id}/results/1.json", params={"limit": limit}
        )
        races = data["MRData"]["RaceTable"]["Races"]
        return [
            {
                "year": int(r["season"]),
                "race": r["raceName"],
                "winner": f"{r['Results'][0]['Driver']['givenName']} "
                f"{r['Results'][0]['Driver']['familyName']}",
                "winner_id": r["Results"][0]["Driver"]["driverId"],
                "constructor": r["Results"][0]["Constructor"]["name"],
            }
            for r in races
            if r.get("Results")
        ]

    @cached(prefix="ergast:driver_circuit", ttl=_WEEK)
    async def get_driver_circuit_results(
        self, driver_id: str, circuit_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """A driver's finishing record at a specific circuit."""
        data = await self._get(
            f"/drivers/{driver_id}/circuits/{circuit_id}/results.json",
            params={"limit": limit},
        )
        races = data["MRData"]["RaceTable"]["Races"]
        out: list[dict[str, Any]] = []
        for r in races:
            res = r["Results"][0] if r.get("Results") else None
            if res is None:
                continue
            out.append(
                {
                    "year": int(r["season"]),
                    "grid": int(res.get("grid", 0)),
                    "position": int(res["position"]),
                    "points": float(res.get("points", 0)),
                    "status": res.get("status"),
                }
            )
        return out


ergast_service = ErgastService()
