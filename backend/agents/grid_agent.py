from __future__ import annotations

import json
import logging

from langchain_anthropic import ChatAnthropic

from agents.state import PredictionState
from config import get_settings
from models.prediction import GridAnalysis
from services import openf1_service

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


def _empty(reason: str) -> dict:
    """Graceful-degradation result — keeps the pipeline running with no grid data.

    This is the normal state for a future race (qualifying hasn't happened yet);
    the prediction then falls back to standings + practice pace.
    """
    return {
        "grid_output": GridAnalysis(
            data_available=False,
            session_analyzed="none",
            is_sprint_weekend=False,
            pole_sitter=None,
            front_row=[],
            grid_order=[],
            sprint_results=None,
            notes=reason,
        ).model_dump()
    }


def _find_session(sessions: list[dict], circuit_id: str, race_name: str) -> dict | None:
    """Match the meeting by circuit/race name — same heuristic as practice_agent."""
    return next(
        (
            s for s in sessions
            if circuit_id.lower().replace("_", " ") in str(s.get("circuit_short_name", "")).lower()
            or race_name.lower() in str(s.get("meeting_name", "")).lower()
        ),
        None,
    )


def _q_best(row: dict) -> float | None:
    """Best qualifying lap from a session_result row.

    OpenF1 qualifying rows carry `duration` as a [Q1, Q2, Q3] array; the driver's
    best is the smallest non-null entry. Race/sprint rows carry a scalar we ignore.
    """
    duration = row.get("duration")
    if isinstance(duration, list):
        times = [t for t in duration if isinstance(t, (int, float))]
        return min(times) if times else None
    return None


async def grid_node(state: PredictionState) -> dict:
    """Read this weekend's actual qualifying grid (+ sprint result) — the strongest signal.

    Grid position is the single biggest predictor of where a driver finishes.
    On sprint weekends the sprint race is a fresh, full-race pace sample. Degrades
    to data_available=False when qualifying hasn't run for this event yet.
    """
    try:
        circuit_id = state["circuit_id"]
        race_name = state["race_name"]
        year = state["year"]

        # 1. Grid: prefer the official starting grid (qualifying + penalties), keyed
        #    off the Race session. Fall back to qualifying-result order if empty.
        race_sessions = await openf1_service.get_sessions(year, "Race")
        race_session = _find_session(race_sessions, circuit_id, race_name)

        quali_sessions = await openf1_service.get_sessions(year, "Qualifying")
        quali_session = _find_session(quali_sessions, circuit_id, race_name)

        quali_result = []
        if quali_session:
            quali_result = await openf1_service.get_session_result(
                quali_session.get("session_key")
            )

        # Best-effort: the official grid can 404 pre-race or 429 under load. Either way
        # we fall back to the qualifying classification below, so never let it bubble up
        # and null the whole (otherwise-available) grid signal.
        grid_rows = []
        if race_session:
            try:
                grid_rows = await openf1_service.get_starting_grid(race_session.get("session_key"))
            except Exception as exc:
                logger.info("starting_grid unavailable (%s) — using qualifying order", exc)

        # Resolve driver_number → full name from whichever session we have entries for.
        entry_session_key = (
            (quali_session or race_session or {}).get("session_key")
        )
        drivers = (
            await openf1_service.get_drivers(entry_session_key) if entry_session_key else []
        )
        number_to_name = {
            d.get("driver_number"): d.get("full_name") or d.get("broadcast_name")
            for d in drivers
        }

        quali_time_by_num = {r.get("driver_number"): _q_best(r) for r in quali_result}

        # Build the grid order: starting_grid if present, else qualifying classification.
        grid = _grid_from_starting_grid(grid_rows, number_to_name, quali_time_by_num)
        if not grid:
            grid = _grid_from_quali_result(quali_result, number_to_name, quali_time_by_num)

        if not grid:
            return _empty("Qualifying has not run for this event yet — no grid available.")

        # 2. Sprint (only some weekends). Its finishing order is a real race-pace sample.
        #    Non-fatal: a sprint fetch failure must not discard the grid signal.
        try:
            sprint_results, is_sprint = await _sprint_results(
                year, circuit_id, race_name, number_to_name
            )
        except Exception as exc:
            logger.info("sprint result unavailable (%s)", exc)
            sprint_results, is_sprint = None, False

        session_label = "Qualifying"
        pole_sitter = grid[0]["driver"]
        front_row = [g["driver"] for g in grid[:2]]

        standings = state.get("driver_standings") or []
        standings_names = [s.get("driver") for s in standings]

        llm = ChatAnthropic(
            model=_MODEL,
            api_key=get_settings().anthropic_api_key,
        ).with_structured_output(GridAnalysis)

        prompt = (
            "You are an expert F1 analyst reading this weekend's qualifying grid and "
            "sprint result. Grid position is the single strongest predictor of the "
            "race result — the front rows almost always dominate the podium.\n\n"
            f"RACE: {race_name} ({year}) | CIRCUIT: {circuit_id}\n\n"
            f"STARTING GRID (pole-first, grid_position 1 = pole):\n"
            f"{json.dumps(grid, indent=2)}\n\n"
            f"SPRINT RACE RESULT (this weekend's real race pace; null if not a sprint weekend):\n"
            f"{json.dumps(sprint_results, indent=2)}\n\n"
            f"CURRENT CHAMPIONSHIP ORDER (driver names, best-first):\n"
            f"{json.dumps(standings_names, indent=2)}\n\n"
            "Summarise what the grid tells us for the race.\n"
            f"- Set data_available=true, session_analyzed='{session_label}', "
            f"is_sprint_weekend={str(is_sprint).lower()}.\n"
            "- pole_sitter and front_row come straight from the grid above.\n"
            "- grid_order: return the drivers in starting order.\n"
            "- sprint_results: pass through the sprint finishing order if present.\n"
            "- notes: flag anything that matters for the race — a grid penalty dropping a "
            "fast driver, a front-row starter who is LOW in the championship (a genuine "
            "dark-horse to win/podium from the front), or a sprint result that contradicts "
            "the championship order. Base every judgement on the data above, not reputation."
        )

        result: GridAnalysis = await llm.ainvoke(prompt)
        logger.info(
            "grid_node done: pole=%s front_row=%s sprint_weekend=%s",
            result.pole_sitter,
            result.front_row,
            result.is_sprint_weekend,
        )
        return {"grid_output": result.model_dump()}

    except Exception as exc:
        logger.error("grid_node failed: %s", exc, exc_info=True)
        return {"grid_output": None}


def _grid_from_starting_grid(
    grid_rows: list[dict], number_to_name: dict, quali_time_by_num: dict
) -> list[dict]:
    """Build the grid order from OpenF1's /starting_grid rows (has `position`)."""
    out = []
    for row in sorted(grid_rows, key=lambda r: r.get("position") or 99):
        num = row.get("driver_number")
        name = number_to_name.get(num)
        pos = row.get("position")
        if not name or pos is None:
            continue
        out.append({
            "driver": name,
            "grid_position": pos,
            "quali_best_time": quali_time_by_num.get(num),
        })
    return out


def _grid_from_quali_result(
    quali_result: list[dict], number_to_name: dict, quali_time_by_num: dict
) -> list[dict]:
    """Fallback grid order from qualifying classification (before /starting_grid fills)."""
    out = []
    for row in sorted(quali_result, key=lambda r: r.get("position") or 99):
        num = row.get("driver_number")
        name = number_to_name.get(num)
        pos = row.get("position")
        if not name or pos is None:
            continue
        out.append({
            "driver": name,
            "grid_position": pos,
            "quali_best_time": quali_time_by_num.get(num),
        })
    return out


async def _sprint_results(
    year: int, circuit_id: str, race_name: str, number_to_name: dict
) -> tuple[list[dict] | None, bool]:
    """Sprint finishing order for the weekend, if a sprint session exists.

    Returns (rows | None, is_sprint_weekend). OpenF1 names the sprint race "Sprint".
    """
    sprint_sessions = await openf1_service.get_sessions(year, "Sprint")
    sprint_session = _find_session(sprint_sessions, circuit_id, race_name)
    if not sprint_session:
        return None, False

    result = await openf1_service.get_session_result(sprint_session.get("session_key"))
    if not result:
        return None, True  # sprint weekend, but the race hasn't run / no result yet

    # Sprint entries may differ from quali entries — resolve names from this session too.
    sprint_drivers = await openf1_service.get_drivers(sprint_session.get("session_key"))
    names = {**number_to_name, **{
        d.get("driver_number"): d.get("full_name") or d.get("broadcast_name")
        for d in sprint_drivers
    }}

    rows = []
    for row in sorted(result, key=lambda r: r.get("position") or 99):
        num = row.get("driver_number")
        name = names.get(num)
        pos = row.get("position")
        if not name or pos is None:
            continue
        rows.append({
            "driver": name,
            "sprint_finish_position": pos,
            "sprint_points": row.get("points"),
        })
    return rows, True
