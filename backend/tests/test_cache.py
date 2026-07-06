"""Unit tests for the @cached decorator — key stability + graceful degradation."""
from __future__ import annotations

import pytest

from services.cache import _make_key, cached


def test_make_key_is_order_independent():
    a = _make_key("p", "fn", (1, 2), {"x": 1, "y": 2})
    b = _make_key("p", "fn", (1, 2), {"y": 2, "x": 1})
    assert a == b


def test_make_key_varies_with_args():
    assert _make_key("p", "fn", (1,), {}) != _make_key("p", "fn", (2,), {})


@pytest.mark.asyncio
async def test_cached_passes_through_when_redis_down(monkeypatch):
    """No Redis → every call runs the function; nothing raises."""
    from database import connection

    monkeypatch.setattr(connection.connections, "redis_client", None, raising=False)

    calls = {"n": 0}

    @cached(prefix="test", ttl=60)
    async def fn(x: int) -> int:
        calls["n"] += 1
        return x * 2

    assert await fn(21) == 42
    assert await fn(21) == 42  # no cache → runs again
    assert calls["n"] == 2
