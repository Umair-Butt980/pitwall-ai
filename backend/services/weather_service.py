from __future__ import annotations

from typing import Any

from config import get_settings
from services.base import BaseHTTPService
from services.cache import cached

# Forecasts update on the provider's side roughly hourly.
_HOUR = 60 * 60


class WeatherService(BaseHTTPService):
    """Weather forecasts from OpenWeatherMap.

    Uses the free 5-day / 3-hour forecast endpoint. Needs OPENWEATHERMAP_API_KEY
    in the environment (see config.py / .env).
    """

    base_url = "https://api.openweathermap.org/data/2.5"

    @cached(prefix="weather:forecast", ttl=_HOUR)
    async def get_forecast(self, lat: float, lon: float) -> list[dict[str, Any]]:
        """3-hourly forecast for the next ~5 days at a location.

        Each entry is trimmed to the fields the weather agent needs:
        time, temperature (°C), conditions, and rain probability (0-1).
        """
        api_key = get_settings().openweathermap_api_key
        if not api_key:
            raise RuntimeError("OPENWEATHERMAP_API_KEY is not configured")

        data = await self._get(
            "/forecast",
            params={
                "lat": lat,
                "lon": lon,
                "appid": api_key,
                "units": "metric",
            },
        )
        out: list[dict[str, Any]] = []
        for entry in data.get("list", []):
            main = entry.get("main") or {}
            weather = (entry.get("weather") or [{}])[0]
            # Skip malformed entries rather than letting one bad slot 500 the call.
            if "dt_txt" not in entry or "temp" not in main:
                continue
            out.append(
                {
                    "time": entry["dt_txt"],
                    "temperature": main["temp"],
                    "conditions": weather.get("main", "Unknown"),
                    "description": weather.get("description", ""),
                    "rain_probability": entry.get("pop", 0),
                }
            )
        return out


weather_service = WeatherService()
