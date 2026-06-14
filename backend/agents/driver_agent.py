from __future__ import annotations

import json
import logging

from langchain_anthropic import ChatAnthropic

from agents.state import PredictionState
from config import get_settings
from models.prediction import DriverAnalysis
from services import ergast_service, fastf1_service

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

# The current 2026 F1 driver lineup — included in every prompt so Claude knows
# exactly who is racing and can produce scores for the right people.
# Update this list at the start of each season.
CURRENT_DRIVERS = [
    "Max Verstappen", "Liam Lawson",          # Red Bull
    "Lewis Hamilton", "Charles Leclerc",       # Ferrari
    "George Russell", "Kimi Antonelli",        # Mercedes
    "Lando Norris", "Oscar Piastri",           # McLaren
    "Fernando Alonso", "Lance Stroll",         # Aston Martin
    "Pierre Gasly", "Jack Doohan",             # Alpine
    "Nico Hulkenberg", "Gabriel Bortoleto",    # Sauber
    "Carlos Sainz", "Alexander Albon",         # Williams
    "Yuki Tsunoda", "Isack Hadjar",            # RB
    "Oliver Bearman", "Esteban Ocon",          # Haas
]


async def driver_node(state: PredictionState) -> dict:
    """Assess driver performance at this circuit using historical data."""
    try:
        circuit_id = state["circuit_id"]
        race_name = state["race_name"]
        year = state["year"]

        # Past race winners at this circuit (all-time)
        circuit_history = await ergast_service.get_circuit_results(circuit_id, limit=50)
        history_text = json.dumps(circuit_history[-20:], indent=2)  # last 20 results

        # Current championship standings + recent winners — the real current-form
        # signal. Read from state (the route fetches these once and shares them).
        standings = state.get("driver_standings") or []
        standings_text = (
            json.dumps(standings, indent=2)
            if standings
            else "Current standings unavailable."
        )
        recent_results = await ergast_service.get_recent_results(year, last_n=5)
        recent_text = (
            json.dumps(recent_results, indent=2)
            if recent_results
            else "Recent results unavailable."
        )

        # Last year's qualifying — supplementary pace signal at this circuit
        try:
            quali_results = await fastf1_service.get_session_results(year - 1, race_name, "Q")
            quali_text = json.dumps(quali_results[:15], indent=2)
        except Exception:
            quali_text = "Qualifying data not available."

        llm = ChatAnthropic(
            model=_MODEL,
            api_key=get_settings().anthropic_api_key,
        ).with_structured_output(DriverAnalysis)

        prompt = (
            f"You are an expert F1 performance analyst.\n\n"
            f"RACE: {race_name} ({year}) | CIRCUIT: {circuit_id}\n\n"
            f"CURRENT DRIVERS RACING THIS SEASON:\n{', '.join(CURRENT_DRIVERS)}\n\n"
            f"CURRENT DRIVER CHAMPIONSHIP STANDINGS ({year}):\n{standings_text}\n\n"
            f"LAST 5 RACE WINNERS THIS SEASON (recent-first):\n{recent_text}\n\n"
            f"PAST WINNERS AT THIS CIRCUIT (recent-first):\n{history_text}\n\n"
            f"LAST YEAR'S QUALIFYING RESULTS:\n{quali_text}\n\n"
            "For each of the current drivers, score their prospects at this circuit.\n"
            "- current_form (0–1): derive STRICTLY from the current championship "
            "standings and recent race winners above. The championship leader and "
            "recent winners must score highest. Do NOT guess from past seasons.\n"
            "- track_wins and track_podiums: derive from the circuit history above.\n"
            "- qualifying_pace (0–1): use last year's qualifying data.\n"
            "- avg_finish_position: realistic value (lower = better).\n"
            "Drivers not in the standings (new/rookie) get low current_form unless "
            "recent results show otherwise."
        )

        result: DriverAnalysis = await llm.ainvoke(prompt)
        logger.info("driver_node done: %d drivers scored", len(result.drivers))
        return {"driver_output": result.model_dump()}

    except Exception as exc:
        logger.error("driver_node failed: %s", exc, exc_info=True)
        return {"driver_output": None}
