from __future__ import annotations

import json
import logging

from langchain_anthropic import ChatAnthropic

from agents.state import PredictionState
from config import get_settings
from models.prediction import TrackAnalysis
from services import ergast_service

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


async def track_node(state: PredictionState) -> dict:
    """Characterise the circuit from recent results + general circuit knowledge.

    Deliberately ignores all-time team dominance: feeding decades of "Ferrari wins
    here" history biased predictions toward perennial winners regardless of current
    form. Only the most recent winners are passed, as a light context signal.
    """
    try:
        circuit_id = state["circuit_id"]
        race_name = state["race_name"]

        history = await ergast_service.get_circuit_results(circuit_id, limit=8)

        summary = {
            "recent_winners": [
                {"year": r["year"], "winner": r["winner"], "team": r["constructor"]}
                for r in sorted(history, key=lambda x: x["year"], reverse=True)
            ],
        }

        llm = ChatAnthropic(
            model=_MODEL,
            api_key=get_settings().anthropic_api_key,
        ).with_structured_output(TrackAnalysis)

        prompt = (
            f"You are an expert F1 circuit analyst.\n\n"
            f"CIRCUIT: {circuit_id} | HOST RACE: {race_name}\n\n"
            f"RECENT WINNERS (context only):\n{json.dumps(summary, indent=2)}\n\n"
            "Characterise this circuit from its known physical layout and your general "
            "F1 knowledge — NOT from which teams have historically dominated it. "
            "Determine circuit_type (e.g. power circuit vs technical, street vs permanent). "
            "Estimate overtaking_difficulty, tire_degradation, and safety_car_probability "
            "based on the circuit's characteristics. "
            "List 3–5 key_characteristics that will influence race strategy."
        )

        result: TrackAnalysis = await llm.ainvoke(prompt)
        logger.info(
            "track_node done: type=%s overtaking=%s", result.circuit_type, result.overtaking_difficulty
        )
        return {"track_output": result.model_dump()}

    except Exception as exc:
        logger.error("track_node failed: %s", exc, exc_info=True)
        return {"track_output": None}
