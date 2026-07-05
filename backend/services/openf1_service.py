from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from services.base import BaseHTTPService
from services.cache import cached

logger = logging.getLogger(__name__)

# Live/recent data, so cache only briefly — just enough to absorb bursts.
_FIVE_MIN = 5 * 60

# OpenF1's anonymous tier rate-limits under bursts. Our pipeline fires several
# OpenF1 calls at once (practice + strategy + grid agents in parallel), so a 429
# is common on the first hit. Back off and retry — once one call succeeds the
# result is cached (5 min) and the burst pressure drops.
_MAX_RETRIES = 4
_BACKOFF_BASE_S = 0.6


class OpenF1Service(BaseHTTPService):
    """Live and recent session data from the OpenF1 API.

    OpenF1 returns flat JSON arrays (no envelope) and filters via query
    params, e.g. /sessions?year=2024&session_name=Race.
    """

    base_url = "https://api.openf1.org/v1"

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """OpenF1 GET with exponential backoff on 429 / transient 5xx."""
        for attempt in range(_MAX_RETRIES):
            try:
                return await super()._get(path, params=params)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                last = attempt == _MAX_RETRIES - 1
                if status not in (429, 500, 502, 503, 504) or last:
                    raise
                delay = _BACKOFF_BASE_S * (2 ** attempt)
                logger.info(
                    "OpenF1 %s on %s — retry %d/%d in %.1fs",
                    status, path, attempt + 1, _MAX_RETRIES - 1, delay,
                )
                await asyncio.sleep(delay)

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

    @cached(prefix="openf1:session_result", ttl=_FIVE_MIN)
    async def get_session_result(self, session_key: int) -> list[dict[str, Any]]:
        """Classification for a finished session (position, points, gap).

        Works for any session type: for qualifying the `duration`/`gap_to_leader`
        fields are [Q1, Q2, Q3] arrays; for a race/sprint they're the total time.
        """
        return await self._get("/session_result", params={"session_key": session_key})

    @cached(prefix="openf1:starting_grid", ttl=_FIVE_MIN)
    async def get_starting_grid(self, session_key: int) -> list[dict[str, Any]]:
        """Starting grid (grid position per driver) — the single strongest race predictor.

        `session_key` here is the RACE session; the grid reflects the qualifying
        result plus any penalties. Populated once qualifying results are official.
        """
        return await self._get("/starting_grid", params={"session_key": session_key})

    @cached(prefix="openf1:session_meta", ttl=_FIVE_MIN)
    async def get_session_meta(self, session_key: int) -> dict[str, Any] | None:
        """The single session record for a session_key (metadata, start/end, circuit)."""
        rows = await self._get("/sessions", params={"session_key": session_key})
        return rows[0] if rows else None

    @cached(prefix="openf1:location", ttl=15)
    async def get_location(
        self,
        session_key: int,
        driver_number: int | None = None,
        date_gte: str | None = None,
        date_lte: str | None = None,
    ) -> list[dict[str, Any]]:
        """Car x/y/z coordinates over time — the raw input for the live track map.

        A whole session is ~35k rows, so callers MUST pass a time window
        (date_gte/date_lte). OpenF1 filters with operator query tokens (`date>=`,
        `date<=`) that don't fit a plain params dict, so we build the query inline.
        """
        query = [f"session_key={session_key}"]
        if driver_number is not None:
            query.append(f"driver_number={driver_number}")
        if date_gte:
            query.append(f"date>={date_gte}")
        if date_lte:
            query.append(f"date<={date_lte}")
        return await self._get("/location?" + "&".join(query))

    @cached(prefix="openf1:position", ttl=_FIVE_MIN)
    async def get_position(self, session_key: int) -> list[dict[str, Any]]:
        """Classification position (P1..P20) over time — running order for the tower."""
        return await self._get("/position", params={"session_key": session_key})


openf1_service = OpenF1Service()
