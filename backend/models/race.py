from __future__ import annotations

from pydantic import BaseModel

# Pydantic models = runtime-validated, self-documenting response shapes.
# Used as FastAPI `response_model`s: FastAPI validates outgoing data against
# them and generates the OpenAPI schema at /docs from them (≈ DTOs in NestJS).


class Race(BaseModel):
    """One round of a season — mirrors the `races` MongoDB collection."""

    name: str
    circuit: str
    circuit_id: str
    location: str
    country: str
    lat: str | None = None
    lon: str | None = None
    date: str
    round: int
    year: int


class CircuitWinner(BaseModel):
    """A past race result at a circuit (winner-focused)."""

    year: int
    race: str
    winner: str
    winner_id: str
    constructor: str


class DriverCircuitResult(BaseModel):
    """A single past finish for a driver at a circuit."""

    year: int
    grid: int
    position: int
    points: float
    status: str | None = None


class DriverCircuitStats(BaseModel):
    """Aggregated stats for a driver at one circuit."""

    driver_id: str
    circuit: str
    starts: int
    wins: int
    podiums: int
    avg_finish: float | None = None
    best_finish: int | None = None
    results: list[DriverCircuitResult]
