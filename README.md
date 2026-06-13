# PitWall AI

> **AI-powered F1 race prediction platform** — six specialized LangGraph agents analyse driver form, weather, car performance, track characteristics and pit strategy, then Claude synthesises it all into a predicted podium with reasoning.

Built as a production-grade portfolio project to learn Python, Docker, and multi-agent AI systems while building something genuinely interesting.

---

## What it does

- Browse the **2026 F1 season calendar** — upcoming and past races
- Click **"Predict the Winner"** on any upcoming race to trigger 6 AI agents in parallel
- Watch each agent complete in real time, then see the **predicted P1/P2/P3 podium** with confidence % and AI reasoning
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
LangGraph Orchestrator  (Phase 3)
    ├── Weather Agent
    ├── Driver Performance Agent
    ├── Car Performance Agent
    ├── Track Analysis Agent
    ├── Strategy Agent
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
| 3 — AI Agents | 🔜 Next | LangGraph orchestrator + 6 agents + Claude prediction |
| 4 — Frontend | 🚧 In progress | Full UI: calendar, standings, predict sheet, history |
| 5 — Polish & Deploy | 🔜 Later | Back-test, EC2 + Vercel deploy, demo video |

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
│   ├── routes/
│   │   ├── health.py
│   │   ├── races.py
│   │   └── drivers.py
│   ├── models/
│   │   └── race.py
│   └── database/
│       └── connection.py      ← Mongo + Redis + httpx singletons
├── frontend/
│   └── src/
│       ├── app/               ← Next.js App Router pages
│       │   ├── page.tsx       ← home: race calendar + next-race hero
│       │   ├── standings/     ← driver + constructor standings
│       │   ├── drivers/[id]/  ← driver circuit stats
│       │   └── history/       ← prediction history
│       ├── components/        ← UI components (MainNav, RaceCard, PredictSheet…)
│       └── lib/api.ts         ← typed API fetchers
├── docs/
│   └── initialScope.md
├── docker-compose.yml
├── .env.example
├── CLAUDE.md                  ← AI assistant reference
└── README.md
```

---

## Learning notes

This project is being built while learning Python and Docker for the first time. The backend code is deliberately commented with JavaScript/NestJS analogies to build a bridge between the known and the new.
