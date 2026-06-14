from __future__ import annotations

import json
import logging
from collections import defaultdict

from langchain_anthropic import ChatAnthropic

from agents.state import PredictionState
from config import get_settings
from models.prediction import CarAnalysis
from services import ergast_service, fastf1_service

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


async def car_node(state: PredictionState) -> dict:
    """Assess constructor performance at this circuit."""
    try:
        race_name = state["race_name"]
        year = state["year"]

        # Last year's race gives team performance + reliability signal.
        try:
            race_results = await fastf1_service.get_session_results(year - 1, race_name, "R")
        except Exception:
            race_results = []

        # Pre-aggregate by team before sending to Claude — keeps the prompt short.
        team_stats: dict[str, dict] = defaultdict(lambda: {"finishes": [], "retirements": 0})
        for row in race_results:
            team = row.get("TeamName", "Unknown")
            status = row.get("Status", "")
            pos = row.get("Position")
            if pos and str(pos).replace(".0", "").isdigit():
                team_stats[team]["finishes"].append(int(float(pos)))
            elif status and status.lower() not in ("", "finished"):
                team_stats[team]["retirements"] += 1

        summary = {
            team: {
                "avg_finish": round(sum(d["finishes"]) / len(d["finishes"]), 1) if d["finishes"] else None,
                "retirements": d["retirements"],
                "drivers_finishing": len(d["finishes"]),
            }
            for team, d in team_stats.items()
        }
        summary_text = json.dumps(summary, indent=2) if summary else "Race data not available for this event."

        # Current constructor championship — the real recent-performance signal.
        standings = state.get("constructor_standings") or []
        standings_text = (
            json.dumps(standings, indent=2)
            if standings
            else "Current constructor standings unavailable."
        )

        llm = ChatAnthropic(
            model=_MODEL,
            api_key=get_settings().anthropic_api_key,
        ).with_structured_output(CarAnalysis)

        prompt = (
            f"You are an F1 technical analyst evaluating constructor performance.\n\n"
            f"RACE: {race_name} ({year}) | CIRCUIT: {state['circuit_id']}\n\n"
            f"CURRENT CONSTRUCTOR CHAMPIONSHIP STANDINGS ({year}):\n{standings_text}\n\n"
            f"LAST YEAR'S RACE AT THIS CIRCUIT — TEAM PERFORMANCE SUMMARY:\n{summary_text}\n\n"
            "Rate each constructor for the current season.\n"
            "- recent_performance (0–1): derive STRICTLY from the current constructor "
            "standings above — the championship leader scores highest. Do NOT rely on "
            "prior-season assumptions.\n"
            "- reliability_score (0–1): base on the retirement counts in last year's "
            "race summary.\n"
            "- car_type: the car's aerodynamic philosophy for this circuit type "
            "(e.g. 'high-downforce', 'low-drag', 'balanced')."
        )

        result: CarAnalysis = await llm.ainvoke(prompt)
        logger.info("car_node done: %d teams scored", len(result.teams))
        return {"car_output": result.model_dump()}

    except Exception as exc:
        logger.error("car_node failed: %s", exc, exc_info=True)
        return {"car_output": None}
