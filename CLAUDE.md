# CLAUDE.md — PitWall AI

AI assistant reference for this codebase. Read this before making changes.

---

## Project overview

PitWall AI is a full-stack F1 race prediction platform. A Next.js frontend calls a
FastAPI backend which orchestrates six LangGraph agents (weather, driver, car, track,
strategy, prediction) to produce a P1/P2/P3 podium prediction backed by Claude Sonnet.

**Current status**: Phase 4 (frontend UI) is in progress. Phase 3 (AI agents) is next.

---

## Folder structure

```
backend/
  main.py              FastAPI app entry point — lifespan, middleware, router mounts
  config.py            All env vars via pydantic-settings (get_settings() singleton)
  database/
    connection.py      Connections class: Mongo + Redis + httpx clients (one shared pool each)
  services/
    cache.py           @cached(prefix, ttl) decorator — wraps async methods, degrades gracefully
    base.py            BaseHTTPService — _get() helper using shared httpx client
    ergast_service.py  Jolpica/Ergast historical data (schedule, circuit results, driver results)
    openf1_service.py  OpenF1 live session data (sessions, weather, stints)
    weather_service.py OpenWeatherMap forecasts
    fastf1_service.py  FastF1 telemetry (SYNC library — always use asyncio.to_thread)
  routes/
    health.py          GET /health
    races.py           GET /api/races, GET /api/races/{circuit_id}/history
    drivers.py         GET /api/drivers/{driver_id}/stats/{circuit}
  models/
    race.py            Pydantic response models (Race, CircuitWinner, DriverStats…)
  agents/              (Phase 3 — not yet built)

frontend/src/
  app/
    layout.tsx         Root layout — sticky MainNav, dark class, Geist fonts
    page.tsx           Home — NextRaceHero + RaceCalendar grid (server component)
    standings/         Tabs: driver standings + constructor standings
    drivers/[driverId] Driver circuit stats (client component, Select + Table)
    history/           Prediction history (empty state until Phase 3)
  components/
    MainNav.tsx        Sticky header — PITWALL AI branding + nav links
    NextRaceHero.tsx   Next upcoming race + live countdown
    RaceCard.tsx       Individual card — past (history panel) or upcoming (predict sheet)
    CircuitHistoryPanel.tsx  Sheet showing past winners at a circuit
    PredictSheet.tsx   Core feature — 6 agent spinner rows → podium reveal
    AgentStatusRow.tsx Single agent row: pending / running (spinner) / done
  lib/
    api.ts             ALL typed API fetchers — keep every backend call here
```

---

## Key patterns

### Backend

**Caching**: Every service method that calls an external API must be decorated with
`@cached(prefix="...", ttl=seconds)` from `services/cache.py`. It reads/writes Redis
transparently and degrades to a pass-through if Redis is down. Never skip this.

**Service singletons**: Each service is instantiated as a module-level singleton at the
bottom of its file (e.g. `ergast_service = ErgastService()`). Import the instance, not
the class: `from services import ergast_service`.

**FastF1 is synchronous**: All `fastf1.*` calls block the thread. Always wrap them in
`asyncio.to_thread(...)`. See `fastf1_service.py` for the pattern.

**Adding new deps**: Edit `backend/requirements.txt`, then rebuild the image:
```bash
docker compose build backend
```
The image installs deps at build time; the source-code volume mount does NOT install
new packages automatically.

**New routes**: Create `backend/routes/<name>.py` with an `APIRouter`, then mount it
in `main.py` with `app.include_router(...)`. Follow the existing style in `races.py`.

**Pydantic models**: Define response shapes in `backend/models/`. Use them as
`response_model=` on route functions so FastAPI validates and documents them.

### Frontend

**All API calls go through `src/lib/api.ts`**. Never call `fetch` directly in a page
or component — add a typed function to `api.ts` first.

**Theme**: Dark mode locked. F1 red primary: `--primary: oklch(0.56 0.24 25)` in
`globals.css`. Do not change the dark background or muted palette.

**UI components**: shadcn/ui only (in `src/components/ui/`). Add new ones with:
```bash
docker compose exec frontend npx shadcn@latest add <component-name> --yes
```

**Server vs client components**: Pages that need `async/await` for data fetching use
server components (no `"use client"`). Components with state, effects, or browser APIs
use `"use client"`. `PredictSheet`, `RaceCard`, `MainNav`, `NextRaceHero`,
`AgentStatusRow`, `CircuitHistoryPanel` are client components.

**Responsive layout**: `max-w-7xl mx-auto px-4 sm:px-6` on page wrappers. Grids:
`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`.

---

## Developer context

- Developer is learning Python and Docker while building this — no prior Python/Docker experience.
- Keep JS/NestJS analogies in backend comments (e.g. `≈ NestJS's ConfigService`).
- Prefer concise code with meaningful names over verbose comments.
- No comments that just restate what the code does — only comments explaining WHY.

---

## What is NOT done yet (Phase 3)

- `backend/agents/` — LangGraph orchestrator + 6 agents
- `POST /api/predictions/predict` — the prediction endpoint
- `GET /api/predictions/history` — prediction history
- `backend/models/prediction.py` — prediction response schema
- Frontend prediction results (currently shows a "Phase 3 coming" placeholder)
- LangChain/Anthropic SDK integration

---

## Running locally

```bash
docker compose up -d          # start all services
docker compose logs backend   # watch backend logs
docker compose exec backend python -c "..."   # run a quick script in context
```

Backend hot-reloads on save (uvicorn --reload + volume mount).
Frontend hot-reloads on save (Next.js dev + volume mount).
