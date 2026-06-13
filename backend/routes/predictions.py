from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.orchestrator import prediction_graph
from agents.state import PredictionState
from database.connection import connections
from models.prediction import PredictionOutput
from services import ergast_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


class PredictRequest(BaseModel):
    race: str   # full race name e.g. "Monaco Grand Prix"
    year: int


@router.post("/predict", response_model=PredictionOutput)
async def predict(body: PredictRequest) -> dict:
    """Run the full multi-agent pipeline and return a podium prediction.

    The five analysis agents run in parallel (≈ Promise.all) and feed their
    outputs to the Claude Sonnet synthesis agent. Typical latency: 15–40s.
    """
    # 1. Resolve circuit metadata (circuit_id, lat, lon) from the season schedule.
    races = await ergast_service.get_season_schedule(body.year)
    race_info = next(
        (r for r in races if r["name"].lower() == body.race.lower()), None
    )
    if race_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"Race '{body.race}' not found in {body.year} season. "
                   "Use the exact name from GET /api/races.",
        )

    lat = float(race_info["lat"]) if race_info.get("lat") else None
    lon = float(race_info["lon"]) if race_info.get("lon") else None

    # 2. Build the initial state — agents fill in the remaining keys.
    initial_state: PredictionState = {
        "race_name": body.race,
        "year": body.year,
        "circuit_id": race_info["circuit_id"],
        "lat": lat,
        "lon": lon,
        "weather_output": None,
        "driver_output": None,
        "car_output": None,
        "track_output": None,
        "strategy_output": None,
        "prediction": None,
        "error": None,
    }

    # 3. Run the graph — blocks until all agents + prediction complete.
    logger.info("Starting prediction pipeline: race=%s year=%d", body.race, body.year)
    final_state: PredictionState = await prediction_graph.ainvoke(initial_state)

    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])
    if not final_state.get("prediction"):
        raise HTTPException(status_code=500, detail="Prediction failed — no output produced")

    # 4. Persist asynchronously so we don't delay the response.
    asyncio.create_task(_save_prediction(body.race, body.year, final_state))

    return final_state["prediction"]


@router.get("/history")
async def prediction_history(limit: int = 20) -> list[dict]:
    """Return the most recent predictions stored in MongoDB."""
    cursor = connections.db["predictions"].find(
        {}, sort=[("created_at", -1)], limit=limit
    )
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


async def _save_prediction(race: str, year: int, state: PredictionState) -> None:
    """Persist the full prediction + agent outputs to the predictions collection."""
    try:
        pred = state["prediction"]
        record = {
            "race": race,
            "year": year,
            "predicted_winner": pred["winner"],
            "predicted_podium": pred["podium"],
            "confidence": pred["confidence"],
            "reasoning": pred["reasoning"],
            "alternative_scenario": pred["alternative_scenario"],
            "driver_probabilities": pred["driver_probabilities"],
            "agents_output": {
                "weather": state.get("weather_output"),
                "driver": state.get("driver_output"),
                "car": state.get("car_output"),
                "track": state.get("track_output"),
                "strategy": state.get("strategy_output"),
            },
            "actual_winner": None,
            "was_correct": None,
            "created_at": datetime.utcnow(),
        }
        await connections.db["predictions"].insert_one(record)
        logger.info("Saved prediction to MongoDB: race=%s winner=%s", race, pred["winner"])
    except Exception as exc:
        logger.error("Failed to save prediction: %s", exc, exc_info=True)
