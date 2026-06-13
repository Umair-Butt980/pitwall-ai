from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ─── Per-agent structured output models ──────────────────────────────────────
# These are used as `with_structured_output(Model)` targets inside each agent.
# Claude fills them in from the raw service data it receives in the prompt.

class WeatherAnalysis(BaseModel):
    temperature: float = Field(description="Expected race-day temperature in °C")
    conditions: str = Field(description="Short weather description e.g. 'Sunny', 'Rainy'")
    rain_probability: float = Field(description="Probability of rain during the race, 0–1")
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


# ─── Final prediction ─────────────────────────────────────────────────────────

class DriverProbability(BaseModel):
    driver: str
    probability: float = Field(description="Win probability 0–1")


class PredictionOutput(BaseModel):
    """Returned by POST /api/predictions/predict and stored in MongoDB."""

    winner: str = Field(description="Predicted race winner (full name)")
    podium: list[str] = Field(description="Predicted P1, P2, P3 (exactly 3 driver names)")
    confidence: float = Field(description="Overall confidence in the prediction 0–1")
    reasoning: str = Field(description="Multi-sentence explanation of the prediction")
    alternative_scenario: str = Field(description="What could change the outcome")
    driver_probabilities: list[DriverProbability] = Field(
        description="Win probability for each of the top 8 drivers"
    )
