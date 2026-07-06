from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment variables (or a .env file).

    Field names map to env vars case-insensitively: mongodb_url <- MONGODB_URL.
    Think of this as NestJS's ConfigService, but validated at startup —
    a missing required var crashes the app immediately instead of at first use.
    """

    environment: str = "development"
    frontend_url: str = "http://localhost:3000"

    mongodb_url: str
    mongodb_db_name: str = "pitwall"
    redis_url: str = "redis://localhost:6379/0"

    # FastF1 keeps its own on-disk cache of downloaded session data (separate
    # from Redis). A docker volume maps to this path so it survives restarts.
    fastf1_cache_dir: str = "/app/.fastf1cache"

    # Required — the prediction pipeline is useless without it, so fail at
    # startup (clear error) rather than deep inside an agent at request time.
    anthropic_api_key: str

    # Optional: the weather agent degrades gracefully when this is missing.
    openweathermap_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    # lru_cache makes this a singleton: the env is read once, every caller
    # after that gets the same Settings object.
    return Settings()
