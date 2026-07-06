"""Shared pytest fixtures.

Sets required env vars before anything imports config, and provides an
httpx client wired to the app via ASGITransport (no network / no real server).
"""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    # Import inside the fixture so the env vars above are set first, and skip
    # the real lifespan (Mongo/Redis/FastF1) — tests mock what they need.
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
