import asyncio

from fastapi import APIRouter

from database.connection import connections

# APIRouter is FastAPI's equivalent of an Express Router / NestJS controller:
# a group of routes you mount onto the main app.
router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness + dependency check.

    Never raises: a down dependency reports "down" with a degraded overall
    status instead of a 500, so monitors can tell *what* is broken.
    """
    # asyncio.gather ≈ Promise.all — both pings run concurrently
    mongo_ok, redis_ok = await asyncio.gather(
        connections.ping_mongo(), connections.ping_redis()
    )
    return {
        "status": "ok" if (mongo_ok and redis_ok) else "degraded",
        "mongo": "ok" if mongo_ok else "down",
        "redis": "ok" if redis_ok else "down",
    }
