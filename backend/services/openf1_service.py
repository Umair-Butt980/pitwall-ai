from __future__ import annotations

from typing import Any

from services.base import BaseHTTPService
from services.cache import cached

# Live/recent data, so cache only briefly — just enough to absorb bursts.
_FIVE_MIN = 5 * 60


class OpenF1Service(BaseHTTPService):
    """Live and recent session data from the OpenF1 API.

    OpenF1 returns flat JSON arrays (no envelope) and filters via query
    params, e.g. /sessions?year=2024&session_name=Race.
    """

    base_url = "https://api.openf1.org/v1"

    @cached(prefix="openf1:sessions", ttl=_FIVE_MIN)
    async def get_sessions(
        self, year: int, session_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Sessions for a year, optionally filtered by name (Race, Qualifying...)."""
        params: dict[str, Any] = {"year": year}
        if session_name:
            params["session_name"] = session_name
        return await self._get("/sessions", params=params)

    @cached(prefix="openf1:weather", ttl=_FIVE_MIN)
    async def get_session_weather(self, session_key: int) -> list[dict[str, Any]]:
        """Track-side weather samples logged during a session."""
        return await self._get("/weather", params={"session_key": session_key})

    @cached(prefix="openf1:stints", ttl=_FIVE_MIN)
    async def get_stints(self, session_key: int) -> list[dict[str, Any]]:
        """Tyre stints (compound + lap ranges) — input for strategy analysis."""
        return await self._get("/stints", params={"session_key": session_key})

    @cached(prefix="openf1:drivers", ttl=_FIVE_MIN)
    async def get_drivers(self, session_key: int) -> list[dict[str, Any]]:
        """Driver entry list for a session — maps driver_number → full_name/team."""
        return await self._get("/drivers", params={"session_key": session_key})

    @cached(prefix="openf1:laps", ttl=_FIVE_MIN)
    async def get_laps(
        self, session_key: int, driver_number: int | None = None
    ) -> list[dict[str, Any]]:
        """Per-lap timing (lap_duration, sectors, speed trap) — input for practice pace."""
        params: dict[str, Any] = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return await self._get("/laps", params=params)


openf1_service = OpenF1Service()
