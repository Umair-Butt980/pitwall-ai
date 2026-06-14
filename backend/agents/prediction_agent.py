from __future__ import annotations

import json
import logging

from langchain_anthropic import ChatAnthropic

from agents.state import PredictionState
from config import get_settings
from models.prediction import PredictionOutput

logger = logging.getLogger(__name__)

# Sonnet 4.6 for the final synthesis — better cross-domain reasoning than Haiku.
_MODEL = "claude-sonnet-4-6"


def _format_section(label: str, data: dict | None) -> str:
    if data is None:
        return f"=== {label} ===\n[Data unavailable — agent did not return results]\n"
    return f"=== {label} ===\n{json.dumps(data, indent=2)}\n"


async def prediction_node(state: PredictionState) -> dict:
    """Synthesise all five agent outputs into a final podium prediction."""
    try:
        race_name = state["race_name"]
        year = state["year"]
        circuit_id = state["circuit_id"]

        # Current standings go FIRST and are framed as the dominant signal — this
        # is what keeps the prediction anchored on who's actually winning this
        # season rather than historical circuit dominance.
        driver_standings = state.get("driver_standings") or []
        constructor_standings = state.get("constructor_standings") or []
        standings_section = (
            "=== CURRENT CHAMPIONSHIP STANDINGS (most important signal) ===\n"
            f"Driver standings:\n{json.dumps(driver_standings[:12], indent=2)}\n\n"
            f"Constructor standings:\n{json.dumps(constructor_standings, indent=2)}\n"
        )

        context = "\n".join([
            standings_section,
            _format_section("WEATHER ANALYSIS", state.get("weather_output")),
            _format_section("DRIVER PERFORMANCE", state.get("driver_output")),
            _format_section("CAR & CONSTRUCTOR PERFORMANCE", state.get("car_output")),
            _format_section("TRACK CHARACTERISTICS", state.get("track_output")),
            _format_section("RACE STRATEGY", state.get("strategy_output")),
        ])

        llm = ChatAnthropic(
            model=_MODEL,
            api_key=get_settings().anthropic_api_key,
        ).with_structured_output(PredictionOutput)

        prompt = (
            "You are PitWall AI — an expert Formula 1 race predictor powered by "
            "multi-agent analysis. You have been given structured analysis from five "
            "specialised agents. Your job is to synthesise this into the definitive "
            "race prediction.\n\n"
            f"RACE: {race_name} | YEAR: {year} | CIRCUIT: {circuit_id}\n\n"
            f"{context}\n"
            "INSTRUCTIONS:\n"
            "1. Predict the exact P1, P2, P3 finishers (podium list must have exactly 3 names).\n"
            "2. The winner field must match podium[0].\n"
            "3. confidence (0–1) should reflect how clear-cut vs. uncertain the outcome is.\n"
            "4. reasoning should be 3–5 sentences explaining the prediction, referencing "
            "   specific insights from the agent analyses.\n"
            "5. alternative_scenario should describe the most plausible upset outcome "
            "   (e.g. safety car, weather change, mechanical failure).\n"
            "6. driver_probabilities must cover the top 8 drivers and sum to approximately 1.0.\n\n"
            "CRITICAL: The current championship standings reflect who is performing NOW "
            "and MUST weigh more heavily than historical circuit dominance. A driver who "
            "dominated this circuit in past seasons but sits mid-table this year is NOT the "
            "favourite. Lead with the current championship leaders and recent winners; only "
            "deviate when weather, strategy, or circuit fit gives a clear, specific reason.\n"
            "Use the current driver names from the standings. Do not include retired or "
            "non-competing drivers."
        )

        result: PredictionOutput = await llm.ainvoke(prompt)
        logger.info(
            "prediction_node done: winner=%s podium=%s confidence=%.2f",
            result.winner,
            result.podium,
            result.confidence,
        )
        return {"prediction": result.model_dump()}

    except Exception as exc:
        logger.error("prediction_node failed: %s", exc, exc_info=True)
        return {"prediction": None, "error": str(exc)}
