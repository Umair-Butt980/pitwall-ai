from __future__ import annotations

import httpx
import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import get_settings


class Connections:
    """Holds the live MongoDB, Redis, and HTTP clients for the whole app.

    One instance of this lives for the lifetime of the process (created on
    startup, closed on shutdown — see the lifespan handler in main.py).
    Each driver keeps its own connection pool internally, so routes can
    share these clients freely across concurrent requests.
    """

    mongo_client: AsyncIOMotorClient | None = None
    redis_client: aioredis.Redis | None = None
    http_client: httpx.AsyncClient | None = None

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self.mongo_client is None:
            raise RuntimeError("MongoDB client not initialized")
        return self.mongo_client[get_settings().mongodb_db_name]

    @property
    def http(self) -> httpx.AsyncClient:
        if self.http_client is None:
            raise RuntimeError("HTTP client not initialized")
        return self.http_client

    async def connect(self) -> None:
        settings = get_settings()
        # Neither constructor opens a socket yet — connections are lazy and
        # happen on the first actual command (like the pings below).
        self.mongo_client = AsyncIOMotorClient(
            settings.mongodb_url, serverSelectionTimeoutMS=5000
        )
        self.redis_client = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
        # One shared client = one connection pool reused across all REST
        # services (≈ a single axios instance for the whole app, not a new
        # one per request). timeout guards against a hung upstream API.
        self.http_client = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        if self.mongo_client is not None:
            self.mongo_client.close()
        if self.redis_client is not None:
            await self.redis_client.aclose()
        if self.http_client is not None:
            await self.http_client.aclose()

    async def ping_mongo(self) -> bool:
        if self.mongo_client is None:
            return False
        try:
            await self.mongo_client.admin.command("ping")
            return True
        except Exception:
            return False

    async def ping_redis(self) -> bool:
        if self.redis_client is None:
            return False
        try:
            return bool(await self.redis_client.ping())
        except Exception:
            return False


connections = Connections()
