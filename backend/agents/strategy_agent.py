from __future__ import annotations

import json
import logging
from collections import Counter

from langchain_anthropic import ChatAnthropic

from agents.state import PredictionState
from config import get_settings
from models.prediction import StrategyAnalysis
from services import openf1_service

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


async def strategy_node(state: PredictionState) -> dict:
    """Model the optimal pit-stop strategy based on tyre data."""
    try:
        circuit_id = state["circuit_id"]
        race_name = state["race_name"]
        year = state["year"]

        # Find last year's race session key via OpenF1.
        sessions = await openf1_service.get_sessions(year - 1, "Race")

        # Match by circuit name substring — OpenF1 uses full circuit names.
        session = next(
            (
                s for s in sessions
                if circuit_id.lower().replace("_", " ") in str(s.get("circuit_short_name", "")).lower()
                or race_name.lower() in str(s.get("meeting_name", "")).lower()
            ),
            sessions[0] if sessions else None,
        )

        if session:
            session_key = session.get("session_key")
            stints_raw = await openf1_service.get_stints(session_key)

            # Aggregate compound usage for the prompt.
            compound_counts = Counter(s.get("compound", "UNKNOWN") for s in stints_raw)
            avg_lap_gap = (
                round(
                    sum(
                        (s.get("lap_end", 0) - s.get("lap_start", 0))
                        for s in stints_raw
                        if s.get("lap_end") and s.get("lap_start")
                    )
                    / max(len(stints_raw), 1)
                )
            )
            strategy_context = {
                "compound_usage": dict(compound_counts.most_common()),
                "avg_stint_length_laps": avg_lap_gap,
                "total_stints_recorded": len(stints_raw),
            }
        else:
            strategy_context = {"note": "No OpenF1 session data found for this event."}

        strategy_text = json.dumps(strategy_context, indent=2)

        llm = ChatAnthropic(
            model=_MODEL,
            api_key=get_settings().anthropic_api_key,
        ).with_structured_output(StrategyAnalysis)

        prompt = (
            f"You are an expert F1 race strategist.\n\n"
            f"RACE: {race_name} ({year}) | CIRCUIT: {circuit_id}\n\n"
            f"LAST YEAR'S TYRE STRATEGY DATA:\n{strategy_text}\n\n"
            "Based on this data and your knowledge of how teams approach this circuit, "
            "determine the optimal strategy. "
            "optimal_pit_windows should be realistic lap numbers for a ~57-70 lap race. "
            "tire_compounds should list the likely compounds in order of use. "
            "Assess whether undercut_opportunity is viable at this circuit. "
            "Describe safety_car_impact on the dominant strategy."
        )

        result: StrategyAnalysis = await llm.ainvoke(prompt)
        logger.info(
            "strategy_node done: pit_windows=%s compounds=%s",
            result.optimal_pit_windows,
            result.tire_compounds,
        )
        return {"strategy_output": result.model_dump()}

    except Exception as exc:
        logger.error("strategy_node failed: %s", exc, exc_info=True)
        return {"strategy_output": None}
