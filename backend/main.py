from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database.connection import connections
from routes import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Everything before `yield` runs at startup, everything after at shutdown —
    # FastAPI's version of NestJS's onModuleInit / onModuleDestroy.
    await connections.connect()
    yield
    await connections.close()


app = FastAPI(
    title="PitWall AI",
    description="AI-powered F1 race prediction — multi-agent LangGraph backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
