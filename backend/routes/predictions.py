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

    # 2. Fetch current-season standings ONCE here and share them via state, so the
    #    agents stay anchored on who is actually winning now (not historical bias).
    try:
        driver_standings = await ergast_service.get_driver_standings(body.year)
        constructor_standings = await ergast_service.get_constructor_standings(body.year)
    except Exception as exc:
        logger.warning("Could not fetch current standings: %s", exc)
        driver_standings, constructor_standings = [], []

    # 3. Build the initial state — agents fill in the remaining keys.
    initial_state: PredictionState = {
        "race_name": body.race,
        "year": body.year,
        "circuit_id": race_info["circuit_id"],
        "lat": lat,
        "lon": lon,
        "driver_standings": driver_standings,
        "constructor_standings": constructor_standings,
        "weather_output": None,
        "driver_output": None,
        "car_output": None,
        "track_output": None,
        "strategy_output": None,
        "practice_output": None,
        "prediction": None,
        "error": None,
    }

    # 4. Run the graph — blocks until all agents + prediction complete.
    logger.info("Starting prediction pipeline: race=%s year=%d", body.race, body.year)
    final_state: PredictionState = await prediction_graph.ainvoke(initial_state)

    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])
    if not final_state.get("prediction"):
        raise HTTPException(status_code=500, detail="Prediction failed — no output produced")

    # 5. Persist asynchronously so we don't delay the response.
    asyncio.create_task(_save_prediction(body.race, body.year, race_info, final_state))

    return final_state["prediction"]


@router.get("/history")
async def prediction_history(limit: int = 20) -> list[dict]:
    """Return recent predictions, grading any whose race has since been run."""
    # Best-effort: fill in actual results for finished races before returning.
    await _grade_pending_predictions()

    cursor = connections.db["predictions"].find(
        {}, sort=[("created_at", -1)], limit=limit
    )
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


async def _grade_pending_predictions() -> None:
    """Backfill actual results for predictions whose race has already happened.

    For every ungraded prediction with a past race date, fetch the real podium
    and record whether we were right. Each item is graded independently so one
    failure can't break the whole history view (≈ the Redis degradation pattern).
    """
    today = datetime.utcnow().date().isoformat()
    cursor = connections.db["predictions"].find(
        {"actual_winner": None, "race_date": {"$lte": today}}
    )
    async for doc in cursor:
        try:
            if not doc.get("round"):
                continue
            result = await ergast_service.get_race_result(doc["year"], doc["round"])
            if result is None:
                continue  # race result not published yet

            actual_podium = result["podium"]
            predicted_podium = doc.get("predicted_podium", [])
            podium_hits = len(set(predicted_podium) & set(actual_podium))

            await connections.db["predictions"].update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "actual_winner": result["winner"],
                    "actual_podium": actual_podium,
                    "was_correct": doc.get("predicted_winner") == result["winner"],
                    "podium_correct_count": podium_hits,
                    "graded_at": datetime.utcnow(),
                }},
            )
            logger.info(
                "Graded prediction: race=%s predicted=%s actual=%s",
                doc.get("race"), doc.get("predicted_winner"), result["winner"],
            )
        except Exception as exc:
            logger.warning("Could not grade prediction %s: %s", doc.get("_id"), exc)


async def _save_prediction(
    race: str, year: int, race_info: dict, state: PredictionState
) -> None:
    """Persist the full prediction + agent outputs to the predictions collection."""
    try:
        pred = state["prediction"]
        record = {
            "race": race,
            "year": year,
            "round": race_info.get("round"),
            "race_date": race_info.get("date"),  # ISO date — used for grading
            "circuit_id": race_info.get("circuit_id"),
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
                "practice": state.get("practice_output"),
            },
            "actual_winner": None,
            "actual_podium": None,
            "was_correct": None,
            "podium_correct_count": None,
            "created_at": datetime.utcnow(),
        }
        await connections.db["predictions"].insert_one(record)
        logger.info("Saved prediction to MongoDB: race=%s winner=%s", race, pred["winner"])
    except Exception as exc:
        logger.error("Failed to save prediction: %s", exc, exc_info=True)
