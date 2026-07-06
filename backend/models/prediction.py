from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ─── Per-agent structured output models ──────────────────────────────────────
# These are used as `with_structured_output(Model)` targets inside each agent.
# Claude fills them in from the raw service data it receives in the prompt.

class WeatherAnalysis(BaseModel):
    temperature: float = Field(description="Expected race-day temperature in °C")
    conditions: str = Field(description="Short weather description e.g. 'Sunny', 'Rainy'")
    rain_probability: float = Field(ge=0, le=1, description="Probability of rain during the race, 0–1")
    wet_race_likely: bool = Field(description="True if wet conditions will significantly affect strategy")


class DriverStat(BaseModel):
    name: str = Field(description="Driver full name")
    track_wins: int = Field(description="Number of wins at this circuit")
    track_podiums: int = Field(description="Number of podiums at this circuit")
    avg_finish_position: float = Field(description="Average finishing position at this circuit")
    current_form: float = Field(description="Current season form score 0–1 (1 = best)")
    qualifying_pace: float = Field(description="Qualifying pace score 0–1 relative to field")


class DriverAnalysis(BaseModel):
    drivers: list[DriverStat] = Field(description="Scored stats for the top F1 drivers")


class TeamStat(BaseModel):
    name: str = Field(description="Constructor name")
    car_type: str = Field(description="Car characteristic e.g. 'high-downforce', 'low-drag'")
    recent_performance: float = Field(description="Recent race performance score 0–1")
    reliability_score: float = Field(description="Mechanical reliability score 0–1")


class CarAnalysis(BaseModel):
    teams: list[TeamStat] = Field(description="Performance ratings for each constructor")


class TrackAnalysis(BaseModel):
    circuit_type: str = Field(description="Circuit type e.g. 'street circuit', 'high-speed'")
    overtaking_difficulty: str = Field(description="'easy', 'medium', or 'hard'")
    tire_degradation: str = Field(description="'low', 'medium', or 'high'")
    safety_car_probability: float = Field(description="Probability of safety car deployment 0–1")
    key_characteristics: list[str] = Field(description="3–5 key features of this circuit")


class StrategyAnalysis(BaseModel):
    optimal_pit_windows: list[int] = Field(description="Lap numbers for optimal pit stops")
    tire_compounds: list[str] = Field(description="Likely compounds to be used e.g. ['soft', 'medium']")
    undercut_opportunity: bool = Field(description="Whether undercut is a viable strategy")
    safety_car_impact: str = Field(description="How a safety car would affect the likely strategy")


class PracticeDriverPace(BaseModel):
    name: str = Field(description="Driver full name")
    best_lap_rank: int = Field(description="1 = fastest single lap in practice (qualifying-sim pace)")
    long_run_pace_rank: int = Field(description="1 = fastest race-stint (high-fuel) pace")
    notes: str = Field(description="Short note e.g. 'topped FP2 long runs', 'missed FP1'")


class PracticeAnalysis(BaseModel):
    """This weekend's free-practice pace — the freshest per-driver signal available."""

    data_available: bool = Field(description="False when no practice has run for this event yet")
    session_analyzed: str = Field(description="Which session was used e.g. 'Practice 2', or 'none'")
    fastest_drivers: list[PracticeDriverPace] = Field(
        description="Top drivers ranked by practice pace (empty if no data)"
    )
    surprise_performers: list[str] = Field(
        description="Drivers quick in practice but low in the championship standings"
    )
    underperformers: list[str] = Field(
        description="Drivers slow in practice relative to their championship standing"
    )
    summary: str = Field(description="One- to three-sentence read of the practice pace picture")


class GridDriver(BaseModel):
    driver: str = Field(description="Driver full name")
    grid_position: int = Field(description="Starting position for the race (1 = pole)")
    quali_best_time: float | None = Field(
        default=None, description="Best qualifying lap in seconds, if available"
    )


class SprintResult(BaseModel):
    driver: str = Field(description="Driver full name")
    sprint_finish_position: int = Field(description="Finishing position in the sprint race")
    sprint_points: float | None = Field(default=None, description="Points scored in the sprint")


class GridAnalysis(BaseModel):
    """This weekend's actual qualifying grid + sprint result — the strongest race signal.

    Grid position is the single biggest predictor of the finishing order for a
    specific race; on sprint weekends the sprint result adds fresh race-pace proof.
    """

    data_available: bool = Field(description="False when qualifying hasn't run for this event yet")
    session_analyzed: str = Field(description="Which session set the grid e.g. 'Qualifying', or 'none'")
    is_sprint_weekend: bool = Field(description="True if a sprint race ran this weekend")
    pole_sitter: str | None = Field(default=None, description="Driver starting P1")
    front_row: list[str] = Field(description="The two drivers on the front row (P1, P2)")
    grid_order: list[GridDriver] = Field(description="Starting grid, pole-first (empty if no data)")
    sprint_results: list[SprintResult] | None = Field(
        default=None, description="Sprint finishing order, if this was a sprint weekend"
    )
    notes: str = Field(
        description="Short read of the grid — penalties, sprint surprises, dark-horses off the front"
    )


# ─── Final prediction ─────────────────────────────────────────────────────────

class DriverProbability(BaseModel):
    driver: str
    probability: float = Field(ge=0, le=1, description="Win probability 0–1")


class PredictionOutput(BaseModel):
    """Returned by POST /api/predictions/predict and stored in MongoDB."""

    winner: str = Field(description="Predicted race winner (full name)")
    podium: list[str] = Field(
        min_length=3, max_length=3,
        description="Predicted P1, P2, P3 (exactly 3 driver names)",
    )
    confidence: float = Field(ge=0, le=1, description="Overall confidence in the prediction 0–1")
    reasoning: str = Field(description="Multi-sentence explanation of the prediction")
    alternative_scenario: str = Field(description="What could change the outcome")
    driver_probabilities: list[DriverProbability] = Field(
        description="Win probability for each of the top 8 drivers"
    )


# ─── Stored prediction history (predicted vs actual) ─────────────────────────

class PredictionHistoryItem(BaseModel):
    """A stored prediction, graded against the real result once the race is run."""

    id: str = Field(description="MongoDB document id")
    race: str
    year: int
    predicted_winner: str
    predicted_podium: list[str]
    confidence: float
    actual_winner: str | None = Field(default=None, description="None until graded")
    actual_podium: list[str] | None = None
    was_correct: bool | None = Field(default=None, description="Winner matched?")
    podium_correct_count: int | None = Field(
        default=None, description="How many of the 3 predicted appear in the real top-3"
    )
    created_at: datetime
