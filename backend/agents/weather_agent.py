from __future__ import annotations

import json
import logging

from agents.llm import HAIKU, get_llm
from agents.state import PredictionState
from models.prediction import WeatherAnalysis
from services import weather_service

logger = logging.getLogger(__name__)


async def weather_node(state: PredictionState) -> dict:
    """Analyse race-day weather and assess its impact on the race."""
    try:
        lat, lon = state.get("lat"), state.get("lon")
        race_name = state["race_name"]

        if lat is None or lon is None:
            logger.warning("weather_node: no coordinates for %s, skipping forecast", race_name)
            forecast_text = "Weather forecast unavailable — circuit coordinates not found."
        else:
            raw = await weather_service.get_forecast(lat, lon)
            # Trim to the next 48 hours (16 × 3h slots) so the prompt stays concise.
            forecast_text = json.dumps(raw[:16], indent=2)

        llm = get_llm(HAIKU).with_structured_output(WeatherAnalysis)

        prompt = (
            f"You are an expert F1 race strategist assessing race-day conditions.\n\n"
            f"RACE: {race_name} ({state['year']})\n\n"
            f"WEATHER FORECAST (3-hourly intervals):\n{forecast_text}\n\n"
            "Analyse the forecast and determine the likely race-day conditions. "
            "If the forecast is unavailable, use your general knowledge of this circuit's typical climate."
        )

        result: WeatherAnalysis = await llm.ainvoke(prompt)
        logger.info("weather_node done: conditions=%s rain_prob=%.2f", result.conditions, result.rain_probability)
        return {"weather_output": result.model_dump()}

    except Exception as exc:
        logger.error("weather_node failed: %s", exc, exc_info=True)
        return {"weather_output": None}
