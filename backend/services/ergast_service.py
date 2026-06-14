from __future__ import annotations

from typing import Any

from services.base import BaseHTTPService
from services.cache import cached

# Past results never change; the season schedule changes rarely.
_DAY = 24 * 60 * 60
_WEEK = 7 * _DAY
# Current-season standings change after every race weekend — keep them fresh.
_SIX_HOURS = 6 * 60 * 60


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

    @cached(prefix="ergast:driver_standings", ttl=_SIX_HOURS)
    async def get_driver_standings(self, year: int) -> list[dict[str, Any]]:
        """Current driver championship standings — who is winning RIGHT NOW."""
        data = await self._get(f"/{year}/driverStandings.json")
        lists = data["MRData"]["StandingsTable"]["StandingsLists"]
        if not lists:
            return []
        return [
            {
                "position": int(s["position"]),
                "points": float(s["points"]),
                "wins": int(s["wins"]),
                "driver": f"{s['Driver']['givenName']} {s['Driver']['familyName']}",
                "driver_id": s["Driver"]["driverId"],
                "team": s["Constructors"][0]["name"] if s.get("Constructors") else "",
            }
            for s in lists[0]["DriverStandings"]
        ]

    @cached(prefix="ergast:constructor_standings", ttl=_SIX_HOURS)
    async def get_constructor_standings(self, year: int) -> list[dict[str, Any]]:
        """Current constructor championship standings."""
        data = await self._get(f"/{year}/constructorStandings.json")
        lists = data["MRData"]["StandingsTable"]["StandingsLists"]
        if not lists:
            return []
        return [
            {
                "position": int(s["position"]),
                "points": float(s["points"]),
                "wins": int(s["wins"]),
                "constructor": s["Constructor"]["name"],
                "constructor_id": s["Constructor"]["constructorId"],
            }
            for s in lists[0]["ConstructorStandings"]
        ]

    @cached(prefix="ergast:recent_results", ttl=_SIX_HOURS)
    async def get_recent_results(
        self, year: int, last_n: int = 5
    ) -> list[dict[str, Any]]:
        """Winners of the most recent races this season (recent-first).

        Uses the /results/1.json endpoint (position == 1) so each race contributes
        exactly its winner — paginating plain /results.json returns per-driver rows.
        """
        data = await self._get(f"/{year}/results/1.json", params={"limit": 100})
        races = data["MRData"]["RaceTable"]["Races"]
        winners = [
            {
                "round": int(r["round"]),
                "race": r["raceName"],
                "winner": f"{r['Results'][0]['Driver']['givenName']} "
                f"{r['Results'][0]['Driver']['familyName']}",
                "constructor": r["Results"][0]["Constructor"]["name"],
            }
            for r in races
            if r.get("Results")
        ]
        return list(reversed(winners))[:last_n]

    @cached(prefix="ergast:race_result", ttl=_WEEK)
    async def get_race_result(self, year: int, round_: int) -> dict[str, Any] | None:
        """The actual top-3 finishers of a specific race, or None if not yet run.

        Used to grade past predictions against reality.
        """
        data = await self._get(f"/{year}/{round_}/results.json")
        races = data["MRData"]["RaceTable"]["Races"]
        if not races or not races[0].get("Results"):
            return None
        results = races[0]["Results"]
        podium = [
            f"{r['Driver']['givenName']} {r['Driver']['familyName']}"
            for r in results[:3]
        ]
        return {
            "race": races[0]["raceName"],
            "winner": podium[0] if podium else None,
            "podium": podium,
            "constructor": results[0]["Constructor"]["name"],
        }


ergast_service = ErgastService()
