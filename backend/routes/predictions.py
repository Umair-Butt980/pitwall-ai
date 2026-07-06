from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.orchestrator import prediction_graph
from agents.state import PredictionState
from database.connection import connections
from models.prediction import PredictionOutput
from rate_limit import limiter
from services import ergast_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])

# Hard server-side deadline for the whole pipeline. Each LLM call is already
# capped at 60s (agents/llm.py); this bounds the request end-to-end so a stuck
# agent can never hold a worker forever.
PIPELINE_TIMEOUT_S = 150

# Every prediction costs ~8 Claude calls, so the trigger endpoints are the
# most expensive thing in the app — keep them strictly rate-limited.
PREDICT_RATE = "5/minute"

# Analysis node name → the state key it writes. Used to unwrap streamed updates.
_NODE_OUTPUT_KEY = {
    "weather": "weather_output",
    "driver": "driver_output",
    "car": "car_output",
    "track": "track_output",
    "strategy": "strategy_output",
    "practice": "practice_output",
    "grid": "grid_output",
}

# asyncio only keeps weak references to tasks — a fire-and-forget
# create_task() with no held reference can be garbage-collected mid-flight.
# Every background task goes through _spawn() so it survives to completion.
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


class PredictRequest(BaseModel):
    race: str = Field(min_length=1, max_length=100)  # e.g. "Monaco Grand Prix"
    year: int = Field(ge=1950, le=2100)


async def _find_existing(race: str, year: int) -> dict | None:
    """Latest stored prediction for this (race, year), matched case-insensitively.

    Best-effort: if Mongo is unreachable the dedup check must not take the
    predict endpoints down with it — we just run the pipeline.
    """
    try:
        return await connections.db["predictions"].find_one(
            {"race": {"$regex": f"^{re.escape(race)}$", "$options": "i"}, "year": year},
            sort=[("created_at", -1)],
        )
    except Exception as exc:
        logger.warning("Dedup lookup failed (continuing without it): %s", exc)
        return None


def _stored_to_output(doc: dict) -> dict:
    """Reshape a stored Mongo doc back into the PredictionOutput response shape."""
    return {
        "winner": doc["predicted_winner"],
        "podium": doc["predicted_podium"],
        "confidence": doc["confidence"],
        "reasoning": doc.get("reasoning", ""),
        "alternative_scenario": doc.get("alternative_scenario", ""),
        "driver_probabilities": doc.get("driver_probabilities", []),
    }


async def _prepare_prediction(race: str, year: int) -> tuple[PredictionState, dict]:
    """Resolve circuit metadata + standings and build the initial graph state.

    Shared by the blocking and streaming predict endpoints. Raises HTTPException(404)
    when the race name doesn't match the season schedule.
    """
    # 1. Resolve circuit metadata (circuit_id, lat, lon) from the season schedule.
    races = await ergast_service.get_season_schedule(year)
    race_info = next((r for r in races if r["name"].lower() == race.lower()), None)
    if race_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"Race '{race}' not found in {year} season. "
                   "Use the exact name from GET /api/races.",
        )

    lat = float(race_info["lat"]) if race_info.get("lat") else None
    lon = float(race_info["lon"]) if race_info.get("lon") else None

    # 2. Fetch current-season standings ONCE here and share them via state, so the
    #    agents stay anchored on who is actually winning now (not historical bias).
    try:
        driver_standings = await ergast_service.get_driver_standings(year)
        constructor_standings = await ergast_service.get_constructor_standings(year)
    except Exception as exc:
        logger.warning("Could not fetch current standings: %s", exc)
        driver_standings, constructor_standings = [], []

    # 3. Build the initial state — agents fill in the remaining keys.
    initial_state: PredictionState = {
        "race_name": race,
        "year": year,
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
        "grid_output": None,
        "prediction": None,
        "error": None,
    }
    return initial_state, race_info


def _sse(payload: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/predict", response_model=PredictionOutput)
@limiter.limit(PREDICT_RATE)
async def predict(request: Request, body: PredictRequest) -> dict:
    """Run the full multi-agent pipeline and return a podium prediction.

    The seven analysis agents run in parallel (≈ Promise.all) and feed their
    outputs to the Claude Sonnet synthesis agent. Typical latency: 15–40s.
    A repeat request for the same race returns the stored prediction instead
    of re-running the pipeline.
    """
    existing = await _find_existing(body.race, body.year)
    if existing:
        logger.info("Returning stored prediction: race=%s year=%d", body.race, body.year)
        return _stored_to_output(existing)

    initial_state, race_info = await _prepare_prediction(body.race, body.year)

    logger.info("Starting prediction pipeline: race=%s year=%d", body.race, body.year)
    try:
        final_state: PredictionState = await asyncio.wait_for(
            prediction_graph.ainvoke(initial_state), timeout=PIPELINE_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Prediction pipeline timed out")

    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])
    if not final_state.get("prediction"):
        raise HTTPException(status_code=500, detail="Prediction failed — no output produced")

    # Persist in the background so we don't delay the response.
    _spawn(_save_prediction(body.race, body.year, race_info, final_state))

    return final_state["prediction"]


@router.get("/predict/stream")
@limiter.limit(PREDICT_RATE)
async def predict_stream(
    request: Request,
    race: str = Query(min_length=1, max_length=100),
    year: int = Query(ge=1950, le=2100),
) -> StreamingResponse:
    """Same pipeline as POST /predict, but stream each agent's result as it finishes.

    Emits Server-Sent Events (text/event-stream): one event per analysis agent as it
    completes (real completion order, since they run in parallel), then a terminal
    event carrying the synthesised podium. The browser consumes this via EventSource.
    A repeat request replays the stored prediction instead of re-running the pipeline.
    """
    existing = await _find_existing(race, year)
    if existing:
        async def replay_gen():
            logger.info("Replaying stored prediction: race=%s year=%d", race, year)
            for agent, output in (existing.get("agents_output") or {}).items():
                yield _sse({"agent": agent, "status": "done", "output": output})
            yield _sse({
                "agent": "prediction",
                "status": "done",
                "cached": True,
                "prediction": _stored_to_output(existing),
            })

        return StreamingResponse(
            replay_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    initial_state, race_info = await _prepare_prediction(race, year)

    async def event_gen():
        logger.info("Starting streamed prediction: race=%s year=%d", race, year)
        final_state: dict = dict(initial_state)
        try:
            # stream_mode="updates" yields {node_name: <the dict the node returned>}
            # the moment each node completes.
            async with asyncio.timeout(PIPELINE_TIMEOUT_S):
                async for chunk in prediction_graph.astream(initial_state, stream_mode="updates"):
                    for node_name, update in chunk.items():
                        if update:
                            final_state.update(update)
                        if node_name == "prediction":
                            continue  # emitted after the loop as the terminal event
                        key = _NODE_OUTPUT_KEY.get(node_name)
                        yield _sse({
                            "agent": node_name,
                            "status": "done",
                            "output": update.get(key) if (update and key) else None,
                        })

            if final_state.get("prediction"):
                _spawn(_save_prediction(race, year, race_info, final_state))
                yield _sse({
                    "agent": "prediction",
                    "status": "done",
                    "prediction": final_state["prediction"],
                })
            else:
                yield _sse({
                    "agent": "prediction",
                    "status": "error",
                    "detail": final_state.get("error") or "Prediction failed — no output produced",
                })
        except TimeoutError:
            logger.error("predict_stream timed out: race=%s year=%d", race, year)
            yield _sse({
                "agent": "prediction",
                "status": "error",
                "detail": "Prediction pipeline timed out",
            })
        except Exception as exc:
            logger.error("predict_stream failed: %s", exc, exc_info=True)
            yield _sse({"agent": "prediction", "status": "error", "detail": str(exc)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering so events flush live
        },
    )


@router.get("/stats")
async def prediction_stats() -> dict:
    """Headline AI-accuracy metrics for the dashboard scorecard.

    Aggregates the graded predictions (those whose race has run) into a small,
    cheap-to-render summary so the homepage doesn't have to pull the full history.
    """
    # Grade newly-finished races in the background — the read itself stays fast
    # and never issues writes; freshly graded rows show up on the next refresh.
    _spawn(_grade_pending_predictions())

    coll = connections.db["predictions"]
    total = await coll.count_documents({})

    graded = [doc async for doc in coll.find({"was_correct": {"$ne": None}})]
    graded_count = len(graded)
    winner_correct = sum(1 for d in graded if d.get("was_correct"))
    podium_hits = sum((d.get("podium_correct_count") or 0) for d in graded)

    by_circuit: dict[str, dict] = {}
    for d in graded:
        cid = d.get("circuit_id") or "unknown"
        bucket = by_circuit.setdefault(
            cid, {"circuit_id": cid, "winner_correct": 0, "graded": 0}
        )
        bucket["graded"] += 1
        if d.get("was_correct"):
            bucket["winner_correct"] += 1

    return {
        "total": total,
        "graded": graded_count,
        "winner_correct": winner_correct,
        "winner_accuracy": (winner_correct / graded_count) if graded_count else 0.0,
        "avg_podium_hits": (podium_hits / graded_count) if graded_count else 0.0,
        "by_circuit": sorted(
            by_circuit.values(), key=lambda x: x["graded"], reverse=True
        ),
    }


@router.get("/history")
async def prediction_history(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    """Return recent predictions, newest first."""
    # Same background-grading pattern as /stats: reads never block on writes.
    _spawn(_grade_pending_predictions())

    cursor = connections.db["predictions"].find(
        {}, sort=[("created_at", -1)], limit=limit
    )
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


@router.post("/grade")
@limiter.limit("10/minute")
async def grade_predictions(request: Request) -> dict:
    """Explicitly grade pending predictions and report how many were graded."""
    graded = await _grade_pending_predictions()
    return {"graded": graded}


async def _grade_pending_predictions(max_items: int = 25) -> int:
    """Backfill actual results for predictions whose race has already happened.

    Grades at most `max_items` per run (oldest first) so a large backlog can't
    turn one call into an unbounded Ergast/Mongo loop; the rest are picked up
    by subsequent runs. Items are graded concurrently and independently so one
    failure can't break the others (≈ the Redis degradation pattern).
    """
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        docs = [
            doc
            async for doc in connections.db["predictions"]
            .find({"actual_winner": None, "race_date": {"$lte": today}})
            .sort("race_date", 1)
            .limit(max_items)
        ]
    except Exception as exc:
        # Runs as a background task — a Mongo outage should log, not crash it.
        logger.warning("Grading scan failed: %s", exc)
        return 0
    if not docs:
        return 0
    results = await asyncio.gather(*(_grade_one(doc) for doc in docs))
    return sum(results)


async def _grade_one(doc: dict) -> bool:
    """Grade a single stored prediction; returns True if it was graded."""
    try:
        if not doc.get("round"):
            return False
        result = await ergast_service.get_race_result(doc["year"], doc["round"])
        if result is None:
            return False  # race result not published yet

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
                "graded_at": datetime.now(timezone.utc),
            }},
        )
        logger.info(
            "Graded prediction: race=%s predicted=%s actual=%s",
            doc.get("race"), doc.get("predicted_winner"), result["winner"],
        )
        return True
    except Exception as exc:
        logger.warning("Could not grade prediction %s: %s", doc.get("_id"), exc)
        return False


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
                "grid": state.get("grid_output"),
            },
            "actual_winner": None,
            "actual_podium": None,
            "was_correct": None,
            "podium_correct_count": None,
            "created_at": datetime.now(timezone.utc),
        }
        await connections.db["predictions"].insert_one(record)
        logger.info("Saved prediction to MongoDB: race=%s winner=%s", race, pred["winner"])
    except Exception as exc:
        logger.error("Failed to save prediction: %s", exc, exc_info=True)
