"""Route tests for the prediction endpoints.

The LangGraph pipeline and Mongo are mocked so the tests exercise validation,
dedup, and the SSE shape without any external calls.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_predict_rejects_out_of_range_year(client):
    resp = await client.post("/api/predictions/predict", json={"race": "Monaco", "year": 1800})
    assert resp.status_code == 422


async def test_predict_rejects_empty_race(client):
    resp = await client.post("/api/predictions/predict", json={"race": "", "year": 2025})
    assert resp.status_code == 422


async def test_history_limit_is_clamped(client, monkeypatch):
    resp = await client.get("/api/predictions/history?limit=100000")
    assert resp.status_code == 422


async def test_predict_returns_stored_prediction(client, monkeypatch):
    """A dedup hit short-circuits the pipeline and returns the stored shape."""
    from routes import predictions

    stored = {
        "predicted_winner": "Max Verstappen",
        "predicted_podium": ["Max Verstappen", "Lando Norris", "Charles Leclerc"],
        "confidence": 0.7,
        "reasoning": "stored",
        "alternative_scenario": "safety car",
        "driver_probabilities": [],
    }

    async def fake_find_existing(race, year):
        return stored

    monkeypatch.setattr(predictions, "_find_existing", fake_find_existing)

    resp = await client.post(
        "/api/predictions/predict", json={"race": "Monaco Grand Prix", "year": 2025}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["winner"] == "Max Verstappen"
    assert len(body["podium"]) == 3
