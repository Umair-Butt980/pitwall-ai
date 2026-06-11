# 🏎️ PitWall AI

AI-powered F1 race prediction platform. Six specialized LangGraph agents
(weather, driver, car, track, strategy, prediction) analyze race data and
predict the podium — P1/P2/P3 with confidence and reasoning.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 · TypeScript · Tailwind CSS · shadcn/ui |
| Backend | Python 3.12 · FastAPI · LangGraph · Claude (Sonnet 4.6 + Haiku 4.5) |
| Data | MongoDB Atlas · Redis · FastF1 · OpenF1 · Jolpica · OpenWeatherMap |
| Infra | Docker Compose · Vercel (frontend) · AWS EC2 (backend) |

## Quickstart

Prerequisites: Docker Desktop, a free [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) cluster.

```bash
# 1. Configure environment
cp .env.example .env          # then fill in MONGODB_URL

# 2. Run everything
docker compose up --build

# 3. Open
#    Frontend  → http://localhost:3000
#    API       → http://localhost:8000/health
#    API docs  → http://localhost:8000/docs
```

## Project structure

```
backend/    FastAPI modular monolith (agents/ services/ routes/ in later phases)
frontend/   Next.js app (App Router, src dir)
docs/       Project scope and planning docs
```

## Roadmap

- [x] Phase 1 — Foundation: Docker Compose, FastAPI + Next.js + Redis + Mongo wired up
- [ ] Phase 2 — Data layer: FastF1 / OpenF1 / Jolpica / weather services with Redis caching
- [ ] Phase 3 — AI agents: LangGraph multi-agent pipeline with live SSE streaming
- [ ] Phase 4 — Frontend: race selector, live agent status, prediction results & charts
- [ ] Phase 5 — Polish + deploy: back-testing, accuracy tracking, Vercel + EC2
