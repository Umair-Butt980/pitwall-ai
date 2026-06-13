"""Data services + their module-level singletons.

Import the ready-to-use instances from here, e.g.
    from services import ergast_service
matching the `connections` singleton pattern in database/connection.py.
"""

from services.ergast_service import ergast_service
from services.fastf1_service import fastf1_service
from services.openf1_service import openf1_service
from services.weather_service import weather_service

__all__ = [
    "ergast_service",
    "fastf1_service",
    "openf1_service",
    "weather_service",
]
