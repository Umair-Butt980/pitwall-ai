from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import fastf1
import pandas as pd

from config import get_settings
from services.cache import cached

logger = logging.getLogger(__name__)

# Historical session data never changes once a race is over, so we can cache
# it in Redis for a long time. FastF1's own disk cache backs this up.
_WEEK = 7 * 24 * 60 * 60


def init_cache() -> None:
    """Point FastF1 at its on-disk cache. Called once at startup (main.py).

    FastF1 downloads several MB of timing/telemetry per session; the disk
    cache means we only pay that cost once per session, ever.
    """
    cache_dir = get_settings().fastf1_cache_dir
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)
    logger.info("FastF1 cache enabled at %s", cache_dir)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe rows.

    Going through to_json handles the awkward cases for us: NaN -> null and
    pandas/NumPy timestamps -> ISO strings, which plain to_dict() does not.
    """
    return json.loads(df.to_json(orient="records", date_format="iso"))


class FastF1Service:
    """Reads F1 session data (results, laps) via the FastF1 library.

    FastF1 is a *synchronous* library doing blocking network + file I/O. If we
    called it directly inside an async route it would freeze the whole event
    loop, so every blocking call runs in a worker thread via asyncio.to_thread
    (≈ offloading to a worker so the main thread stays responsive).
    """

    @cached(prefix="fastf1:results", ttl=_WEEK)
    async def get_session_results(
        self, year: int, event: str | int, session: str = "R"
    ) -> list[dict[str, Any]]:
        """Final classification for a session.

        event: GP name ("Monaco") or round number. session: "R" race,
        "Q" qualifying, "S" sprint, etc.
        """
        return await asyncio.to_thread(self._load_results, year, event, session)

    # Runs in a worker thread — keep it fully synchronous (no await here).
    def _load_results(
        self, year: int, event: str | int, session: str
    ) -> list[dict[str, Any]]:
        ses = fastf1.get_session(year, event, session)
        ses.load(laps=False, telemetry=False, weather=False, messages=False)
        results = ses.results
        # Keep the columns the agents actually use; the full frame is wide.
        columns = [
            "Abbreviation",
            "FullName",
            "TeamName",
            "GridPosition",
            "Position",
            "Points",
            "Status",
            "Time",
        ]
        present = [c for c in columns if c in results.columns]
        return _records(results[present])


fastf1_service = FastF1Service()
