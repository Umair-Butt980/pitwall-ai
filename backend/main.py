import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import get_settings
from database.connection import connections
from rate_limit import limiter
from routes import drivers, health, live, predictions, races, standings
from services.fastf1_service import init_cache as init_fastf1_cache

# Without this, every logger.info/debug in the app is silently discarded —
# Python's default root logger only shows WARNING and above.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

_request_log = logging.getLogger("pitwall.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Everything before `yield` runs at startup, everything after at shutdown —
    # FastAPI's version of NestJS's onModuleInit / onModuleDestroy.
    await connections.connect()
    init_fastf1_cache()
    yield
    await connections.close()


app = FastAPI(
    title="PitWall AI",
    description="AI-powered F1 race prediction — multi-agent LangGraph backend",
    version="0.1.0",
    lifespan=lifespan,
)

# Per-IP rate limiting — the prediction endpoints fire ~8 Claude calls each,
# so an unmetered public endpoint is an open cost-DoS vector.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One structured line per request with method, path, status, and latency."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    _request_log.info(
        "%s %s → %d (%.0fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response

app.include_router(health.router)
app.include_router(races.router)
app.include_router(drivers.router)
app.include_router(predictions.router)
app.include_router(live.router)
app.include_router(standings.router)
