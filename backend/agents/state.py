from __future__ import annotations

from typing import TypedDict


class PredictionState(TypedDict):
    """Shared state that flows through the LangGraph prediction pipeline.

    Think of this like a NestJS request context object — every node in the
    graph reads from it and writes its own slice back. LangGraph merges each
    node's partial return dict into this shared state automatically.

    Fan-out / fan-in:
      START → [weather, driver, car, track, strategy] run in parallel
           → each writes only its own *_output key
           → prediction node reads all five, writes `prediction`
           → END
    """

    # ── Inputs (set by the route before invoking the graph) ──────────────────
    race_name: str
    year: int
    circuit_id: str
    lat: float | None   # used by weather agent for the forecast API
    lon: float | None

    # ── Current-season grounding (fetched once by the route, read-only) ──────
    # These anchor the agents on who is actually winning NOW, so scores aren't
    # hallucinated from the model's training cutoff.
    driver_standings: list | None
    constructor_standings: list | None

    # ── Parallel agent outputs (None until the agent completes) ──────────────
    weather_output: dict | None
    driver_output: dict | None
    car_output: dict | None
    track_output: dict | None
    strategy_output: dict | None

    # ── Final synthesis ───────────────────────────────────────────────────────
    prediction: dict | None
    error: str | None
