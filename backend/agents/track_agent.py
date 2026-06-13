from __future__ import annotations

import json
import logging
from collections import Counter

from langchain_anthropic import ChatAnthropic

from agents.state import PredictionState
from config import get_settings
from models.prediction import TrackAnalysis
from services import ergast_service

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


async def track_node(state: PredictionState) -> dict:
    """Characterise the circuit based on its full race history."""
    try:
        circuit_id = state["circuit_id"]
        race_name = state["race_name"]

        history = await ergast_service.get_circuit_results(circuit_id, limit=100)

        # Extract patterns Claude can reason over.
        constructor_wins = Counter(r["constructor"] for r in history)
        top_constructors = constructor_wins.most_common(5)
        total_races = len(history)

        summary = {
            "total_races_held": total_races,
            "most_successful_constructors": [
                {"team": t, "wins": w} for t, w in top_constructors
            ],
            "recent_winners": [
                {"year": r["year"], "winner": r["winner"], "team": r["constructor"]}
                for r in sorted(history, key=lambda x: x["year"], reverse=True)[:10]
            ],
        }

        llm = ChatAnthropic(
            model=_MODEL,
            api_key=get_settings().anthropic_api_key,
        ).with_structured_output(TrackAnalysis)

        prompt = (
            f"You are an expert F1 circuit analyst.\n\n"
            f"CIRCUIT: {circuit_id} | HOST RACE: {race_name}\n\n"
            f"CIRCUIT HISTORY SUMMARY:\n{json.dumps(summary, indent=2)}\n\n"
            "Characterise this circuit. Use the historical dominance by certain teams to infer "
            "circuit type (e.g. power circuit vs technical, street vs permanent). "
            "Estimate overtaking_difficulty, tire_degradation, and safety_car_probability "
            "based on the circuit's known characteristics. "
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
