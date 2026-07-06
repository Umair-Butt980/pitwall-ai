# PitWall AI

> **AI-powered F1 race prediction platform** — seven specialized LangGraph agents (weather, driver, car, track, strategy, practice pace, and qualifying grid) run in parallel on Claude Haiku, then a Claude Sonnet synthesis agent turns their analyses into a predicted podium with reasoning.

Built as a production-grade portfolio project to learn Python, Docker, and multi-agent AI systems while building something genuinely interesting.

---

## What it does

- Browse the **2026 F1 season calendar** — upcoming and past races
- Click **"Predict the Winner"** on any upcoming race to trigger 7 analysis agents in parallel
- Watch each agent complete in real time (streamed over SSE), then see the **predicted P1/P2/P3 podium** with confidence % and AI reasoning
- Open the **Live Race Center** to watch cars plotted on a track map from OpenF1 positional data
- View **Championship Standings** (Drivers & Constructors)
- Browse **circuit history** — every past winner at a circuit going back to the 1950s
- Drill into **driver stats** at any circuit (starts, wins, podiums, race-by-race results)
- Review **prediction history** — compare AI picks vs actual results over time

---

## Architecture

```
Browser (Next.js)
    │
    ▼
FastAPI Backend (Python 3.12)
    │
    ├── Ergast/Jolpica API ──── historical schedule, standings, circuit results
    ├── OpenF1 API ─────────── live session data, tyre stints
    ├── OpenWeatherMap API ──── race-day forecast
    └── FastF1 library ──────── telemetry, qualifying, lap data
    │
    ▼
LangGraph Orchestrator  (fan-out → fan-in)
    ├── Weather Agent            ┐
    ├── Driver Performance Agent │
    ├── Car Performance Agent    │  7 analysis agents run in parallel
    ├── Track Analysis Agent     │  on Claude Haiku (one LangGraph superstep)
    ├── Strategy Agent           │
    ├── Practice Pace Agent      │
    ├── Qualifying Grid Agent    ┘
    └── Prediction Agent ──── Claude Sonnet (final synthesis)
    │
    ▼
MongoDB Atlas ──── stores predictions + race data
Redis ──────────── caches API responses (per-service TTLs)
```

---

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python 3.12, FastAPI, async (uvicorn) |
| AI Agents | LangGraph, Claude Sonnet (via Anthropic SDK) |
| Data | FastF1, OpenF1 API, Jolpica/Ergast API, OpenWeatherMap |
| Database | MongoDB Atlas (free tier) |
| Cache | Redis |
| DevOps | Docker Compose (local), AWS EC2 + Vercel (prod) |

---

## Quickstart

### Prerequisites
- Docker + Docker Compose
- MongoDB Atlas cluster (free tier) — [create one here](https://www.mongodb.com/atlas)
- API keys: OpenWeatherMap (Phase 2+), Anthropic (Phase 3+)

### 1. Clone & configure
```bash
git clone https://github.com/UmairButt980/pitwall-ai.git
cd pitwall-ai
cp .env.example .env
# Edit .env — fill in MONGODB_URL, OPENWEATHERMAP_API_KEY, ANTHROPIC_API_KEY
```

### 2. Run
```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `MONGODB_URL` | ✅ | Atlas connection string |
| `MONGODB_DB_NAME` | optional | Defaults to `pitwall` |
| `REDIS_URL` | optional | Defaults to local Redis in compose |
| `OPENWEATHERMAP_API_KEY` | ✅ Phase 2+ | Free at openweathermap.org |
| `ANTHROPIC_API_KEY` | ✅ Phase 3+ | Claude API key |
| `FRONTEND_URL` | optional | Defaults to `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | optional | Defaults to `http://localhost:8000` |
| `FASTF1_CACHE_DIR` | optional | Defaults to `/app/.fastf1cache` |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness + dependency check |
| `GET` | `/api/races?year=2026` | Season race calendar |
| `GET` | `/api/races/{circuit_id}/history` | Past winners at a circuit |
| `GET` | `/api/drivers/{driver_id}/stats/{circuit}` | Driver stats at a circuit |
| `POST` | `/api/predictions/predict` | Trigger multi-agent prediction *(Phase 3)* |
| `GET` | `/api/predictions/history` | Past predictions + accuracy *(Phase 3)* |

Full interactive docs at `http://localhost:8000/docs`.

---

## Development phases

| Phase | Status | Description |
|---|---|---|
| 1 — Foundation | ✅ Done | FastAPI + Next.js + Docker Compose + MongoDB + Redis |
| 2 — Data Layer | ✅ Done | 4 data services + Redis caching + races/drivers routes |
| 3 — AI Agents | ✅ Done | LangGraph orchestrator + 7 analysis agents + Claude synthesis + SSE streaming |
| 4 — Frontend | ✅ Done | Full UI: calendar, standings, predict sheet, history, live race center |
| 5 — Polish & Deploy | 🚧 In progress | Prod Dockerfiles + compose, CI, tests, rate limiting, deploy |

---

## Project structure

```
pitwall-ai/
├── backend/
│   ├── main.py                ← FastAPI app + lifespan
│   ├── config.py              ← env vars (pydantic-settings)
│   ├── services/
│   │   ├── cache.py           ← @cached decorator (Redis)
│   │   ├── base.py            ← BaseHTTPService (shared httpx client)
│   │   ├── ergast_service.py  ← Jolpica/Ergast historical data
│   │   ├── openf1_service.py  ← live session data
│   │   ├── weather_service.py ← OpenWeatherMap forecasts
│   │   └── fastf1_service.py  ← telemetry (sync → asyncio.to_thread)
│   ├── agents/                ← LangGraph pipeline
│   │   ├── orchestrator.py    ← fan-out/fan-in graph (compiled once)
│   │   ├── llm.py             ← shared capped ChatAnthropic clients
│   │   ├── state.py           ← PredictionState TypedDict
│   │   └── *_agent.py         ← 7 analysis agents + prediction synthesis
│   ├── routes/
│   │   ├── health.py          ← /health (liveness) + /ready (readiness)
│   │   ├── races.py
│   │   ├── drivers.py
│   │   ├── predictions.py     ← /predict, /predict/stream (SSE), /history, /stats, /grade
│   │   ├── standings.py       ← cached driver/constructor standings proxy
│   │   └── live.py            ← live race center (OpenF1 positional data)
│   ├── models/
│   │   ├── race.py
│   │   └── prediction.py      ← agent output + prediction response schemas
│   ├── rate_limit.py          ← slowapi per-IP limiter
│   ├── tests/                 ← pytest (routes via ASGITransport + cache units)
│   └── database/
│       └── connection.py      ← Mongo + Redis + httpx singletons
├── frontend/
│   └── src/
│       ├── app/               ← Next.js App Router pages
│       │   ├── page.tsx       ← home: race calendar + next-race hero
│       │   ├── error.tsx      ← root error boundary + loading.tsx skeleton
│       │   ├── standings/     ← driver + constructor standings
│       │   ├── drivers/[id]/  ← driver circuit stats
│       │   ├── live/          ← live race center
│       │   └── history/       ← prediction history
│       ├── components/        ← UI components (MainNav, RaceCard, PredictSheet…)
│       └── lib/api.ts         ← typed API fetchers
├── docs/
│   ├── architecture.md        ← system design (current)
│   ├── future-features.md     ← the one-stop-platform roadmap
│   └── feature-*.md           ← per-feature specs (live timing is next up)
├── docker-compose.yml         ← dev (hot reload)
├── docker-compose.prod.yml    ← prod (restart policies, limits, healthchecks)
├── backend/Dockerfile.prod    ← multi-worker, non-root, healthcheck
├── frontend/Dockerfile.prod   ← multi-stage standalone build
├── .github/workflows/ci.yml   ← lint + typecheck + pytest + build
├── .env.example
├── CLAUDE.md                  ← AI assistant reference
└── README.md
```

---

## Learning notes

This project is being built while learning Python and Docker for the first time. The backend code is deliberately commented with JavaScript/NestJS analogies to build a bridge between the known and the new.
