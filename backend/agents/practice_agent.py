from __future__ import annotations

import json
import logging
from statistics import median

from langchain_anthropic import ChatAnthropic

from agents.state import PredictionState
from config import get_settings
from models.prediction import PracticeAnalysis
from services import openf1_service

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

# Prefer the session with the most representative running. FP2 usually has the
# best mix of qualifying sims + high-fuel long runs; fall back through the others.
_PRACTICE_SESSIONS = ["Practice 2", "Practice 3", "Practice 1"]

# A "long run" needs enough consecutive timed laps to reflect race pace, not a sim.
_MIN_LONG_RUN_LAPS = 5


def _empty(reason: str) -> dict:
    """Graceful-degradation result — keeps the pipeline running with no practice data."""
    return {
        "practice_output": PracticeAnalysis(
            data_available=False,
            session_analyzed="none",
            fastest_drivers=[],
            surprise_performers=[],
            underperformers=[],
            summary=reason,
        ).model_dump()
    }


def _find_session(sessions: list[dict], circuit_id: str, race_name: str) -> dict | None:
    """Match the meeting by circuit/race name — same heuristic as strategy_agent."""
    return next(
        (
            s for s in sessions
            if circuit_id.lower().replace("_", " ") in str(s.get("circuit_short_name", "")).lower()
            or race_name.lower() in str(s.get("meeting_name", "")).lower()
        ),
        None,
    )


async def practice_node(state: PredictionState) -> dict:
    """Analyse this weekend's free-practice pace — the freshest per-driver signal.

    Pace IN practice reflects current upgrades and track-specific setup, so it's
    what lets the prediction deviate from the (slow-moving) championship standings.
    Degrades to data_available=False when practice hasn't run for this event yet.
    """
    try:
        circuit_id = state["circuit_id"]
        race_name = state["race_name"]
        year = state["year"]

        # Find the most representative practice session that exists for this event.
        session = None
        session_label = "none"
        for name in _PRACTICE_SESSIONS:
            sessions = await openf1_service.get_sessions(year, name)
            match = _find_session(sessions, circuit_id, race_name)
            if match:
                session, session_label = match, name
                break

        if session is None:
            return _empty("No free-practice session found for this event yet.")

        session_key = session.get("session_key")
        laps = await openf1_service.get_laps(session_key)
        drivers = await openf1_service.get_drivers(session_key)

        if not laps:
            return _empty(f"{session_label} found but no lap data is available yet.")

        number_to_name = {
            d.get("driver_number"): d.get("full_name") or d.get("broadcast_name")
            for d in drivers
        }

        pace = _aggregate_pace(laps, number_to_name)
        if not pace:
            return _empty(f"{session_label} lap data was too sparse to rank pace.")

        best_ranked = sorted(pace.values(), key=lambda p: p["best_lap"])
        long_run_ranked = sorted(
            (p for p in pace.values() if p["long_run"] is not None),
            key=lambda p: p["long_run"],
        )
        best_rank = {p["name"]: i + 1 for i, p in enumerate(best_ranked)}
        long_rank = {p["name"]: i + 1 for i, p in enumerate(long_run_ranked)}

        # Compact per-driver table for the prompt — top ~12 by single-lap pace.
        table = [
            {
                "name": p["name"],
                "best_lap_rank": best_rank[p["name"]],
                "long_run_pace_rank": long_rank.get(p["name"], None),
                "timed_laps": p["timed_laps"],
            }
            for p in best_ranked[:12]
        ]

        standings = state.get("driver_standings") or []
        standings_names = [s.get("driver") for s in standings]

        llm = ChatAnthropic(
            model=_MODEL,
            api_key=get_settings().anthropic_api_key,
        ).with_structured_output(PracticeAnalysis)

        prompt = (
            "You are an expert F1 analyst reading free-practice timing data.\n\n"
            f"RACE: {race_name} ({year}) | CIRCUIT: {circuit_id} | SESSION: {session_label}\n\n"
            f"PRACTICE PACE (best_lap_rank = single-lap/quali-sim pace, "
            f"long_run_pace_rank = high-fuel race pace; 1 = fastest):\n"
            f"{json.dumps(table, indent=2)}\n\n"
            f"CURRENT CHAMPIONSHIP ORDER (driver names, best-first):\n"
            f"{json.dumps(standings_names, indent=2)}\n\n"
            "Summarise the practice pace picture.\n"
            "- fastest_drivers: rank the quickest drivers this weekend using BOTH lap "
            "ranks (favour long-run pace for race outcome). Set data_available=true and "
            f"session_analyzed='{session_label}'.\n"
            "- surprise_performers: drivers fast in practice but LOW in the championship "
            "order — these are legitimate dark-horses for this race.\n"
            "- underperformers: drivers near the top of the championship but slow in "
            "practice this weekend.\n"
            "Base every judgement on the practice data above, not on reputation."
        )

        result: PracticeAnalysis = await llm.ainvoke(prompt)
        logger.info(
            "practice_node done: session=%s drivers_ranked=%d surprises=%s",
            session_label,
            len(result.fastest_drivers),
            result.surprise_performers,
        )
        return {"practice_output": result.model_dump()}

    except Exception as exc:
        logger.error("practice_node failed: %s", exc, exc_info=True)
        return {"practice_output": None}


def _aggregate_pace(laps: list[dict], number_to_name: dict) -> dict:
    """Per-driver best-lap + long-run median from raw OpenF1 lap rows.

    OpenF1 lap rows carry `lap_duration` (seconds, may be null on in/out laps),
    `is_pit_out_lap`, and `lap_number`. We compute single-lap pace (min valid lap)
    and race pace (median of the longest run of clean consecutive laps).
    """
    by_driver: dict[int, list[dict]] = {}
    for lap in laps:
        num = lap.get("driver_number")
        if num is None:
            continue
        by_driver.setdefault(num, []).append(lap)

    pace: dict[int, dict] = {}
    for num, driver_laps in by_driver.items():
        name = number_to_name.get(num)
        if not name:
            continue

        clean = [
            lap for lap in driver_laps
            if lap.get("lap_duration") and not lap.get("is_pit_out_lap")
        ]
        if not clean:
            continue

        durations = [lap["lap_duration"] for lap in clean]
        best_lap = min(durations)
        long_run = _longest_run_median(clean)

        pace[num] = {
            "name": name,
            "best_lap": best_lap,
            "long_run": long_run,
            "timed_laps": len(clean),
        }
    return pace


def _longest_run_median(clean_laps: list[dict]) -> float | None:
    """Median lap time of the longest streak of consecutive clean laps (race-pace proxy).

    Filters in-lap/out-lap noise by requiring consecutive lap numbers; ignores the
    fastest lap of the run (a likely push lap) so the figure reflects sustained pace.
    """
    ordered = sorted(clean_laps, key=lambda lap: lap.get("lap_number") or 0)

    best_run: list[dict] = []
    current: list[dict] = []
    prev_num: int | None = None
    for lap in ordered:
        num = lap.get("lap_number")
        if prev_num is not None and num == prev_num + 1:
            current.append(lap)
        else:
            current = [lap]
        if len(current) > len(best_run):
            best_run = list(current)
        prev_num = num

    if len(best_run) < _MIN_LONG_RUN_LAPS:
        return None

    times = sorted(lap["lap_duration"] for lap in best_run)
    return median(times[1:])  # drop the single quickest lap of the stint
