from __future__ import annotations

import functools
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from database.connection import connections

logger = logging.getLogger(__name__)

# TypeVar lets the decorator preserve the wrapped function's return type for
# editors/type-checkers — `cached(...)(fn)` has the same signature as `fn`.
R = TypeVar("R")


def _make_key(prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """Build a stable Redis key from the call's arguments.

    Two calls with the same args produce the same key. We JSON-encode the
    args (sort_keys so {a:1,b:2} and {b:2,a:1} match) and hash them so the
    key stays short and safe regardless of how big the args are.
    """
    raw = json.dumps([args, kwargs], sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}:{func_name}:{digest}"


def cached(prefix: str, ttl: int) -> Callable[[Callable[..., Awaitable[R]]], Callable[..., Awaitable[R]]]:
    """Cache an async function's return value in Redis for `ttl` seconds.

    This is a *decorator factory*: `cached(prefix, ttl)` returns the actual
    decorator, which wraps your function. Think of it like a NestJS
    interceptor — it runs around the original call, short-circuiting with a
    cached value on a hit and storing the result on a miss.

    The wrapped function must be `async` and must return JSON-serializable
    data (dict / list / str / number / bool / None). Convert pandas objects
    to plain dicts/lists *before* returning.

    Redis is treated as best-effort: if it's down, every call is a miss and
    we just run the function — mirrors the graceful degradation in
    database/connection.py's ping_* methods.
    """

    def decorator(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
        # functools.wraps copies func's name/docstring onto the wrapper so it
        # still looks like the original (matters for FastAPI + debugging).
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> R:
            key = _make_key(prefix, func.__name__, args, kwargs)
            redis = connections.redis_client

            # 1. Try cache (best-effort).
            if redis is not None:
                try:
                    hit = await redis.get(key)
                    if hit is not None:
                        logger.debug("cache hit: %s", key)
                        return json.loads(hit)
                except Exception:
                    logger.warning("cache read failed for %s; skipping", key)

            # 2. Miss → run the real function.
            logger.debug("cache miss: %s", key)
            result = await func(*args, **kwargs)

            # 3. Store (best-effort). SETEX = SET + expiry in one command.
            if redis is not None:
                try:
                    await redis.setex(key, ttl, json.dumps(result, default=str))
                except Exception:
                    logger.warning("cache write failed for %s; skipping", key)

            return result

        return wrapper

    return decorator
