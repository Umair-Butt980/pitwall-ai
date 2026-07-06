# CLAUDE.md — PitWall AI

AI assistant reference for this codebase. Read this before making changes.

---

## Project overview

PitWall AI is a full-stack F1 race prediction platform. A Next.js frontend calls a
FastAPI backend which orchestrates six LangGraph agents (weather, driver, car, track,
strategy, prediction) to produce a P1/P2/P3 podium prediction backed by Claude Sonnet.

**Current status**: Phases 1–4 are done (data layer, 7-agent pipeline, full UI incl. live
race center). Phase 5 (production hardening) is in progress — prod Dockerfiles/compose, CI,
tests, rate limiting, and observability are in place; deploy is pending.

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
    health.py          GET /health (liveness, always 200), GET /ready (503 if Mongo down)
    races.py           GET /api/races, /api/races/result, /api/races/{circuit_id}/history
    drivers.py         GET /api/drivers/{driver_id}/stats/{circuit}
    predictions.py     POST /predict, GET /predict/stream (SSE), /history, /stats, POST /grade
    standings.py       GET /api/standings/drivers, /api/standings/constructors (cached proxy)
    live.py            live race center — sessions, track outline, positional map (OpenF1)
  models/
    race.py            Pydantic response models (Race, CircuitWinner, DriverStats…)
    prediction.py      Per-agent structured-output models + PredictionOutput (with Field bounds)
  rate_limit.py        slowapi Limiter singleton (per-IP); wired in main.py
  agents/
    orchestrator.py    LangGraph fan-out/fan-in graph, compiled once at import
    llm.py             get_llm(model, max_tokens) — shared capped ChatAnthropic clients
    state.py           PredictionState TypedDict
    <domain>_agent.py  7 analysis agents (weather/driver/car/track/strategy/practice/grid)
    prediction_agent.py  Claude Sonnet synthesis node
  tests/               pytest — routes via httpx ASGITransport, cache units

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
Add `Field(...)` constraints (bounds, lengths) — they double as input validation
and as guardrails on LLM structured output.

**LLM calls**: Never construct `ChatAnthropic` inline. Use
`get_llm(model, max_tokens)` from `agents/llm.py` — it returns capped, reused
clients (`timeout`, `max_retries`, `max_tokens` all set). Uncapped LLM calls on a
public endpoint are a cost-DoS vector.

**Rate limiting**: The prediction endpoints fire ~8 LLM calls each. Decorate any
new expensive/LLM-backed route with `@limiter.limit("N/minute")` (from
`rate_limit.py`) and give it a `request: Request` param (slowapi needs it).

**Background work**: Don't `asyncio.create_task(...)` fire-and-forget — the loop
only weakly references tasks, so they can be GC'd mid-flight. Use `_spawn()` in
`predictions.py` (holds a ref until done) or `await` inline. Never grade/write on
a GET path — do it in the background or an explicit `POST`.

**Tests**: `docker compose exec backend python -m pytest`. Route tests use httpx
`ASGITransport` (no live server); mock the pipeline/Mongo rather than calling them.

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

## What is NOT done yet (Phase 5)

- Deploy target — prod Dockerfiles/compose exist (`*.prod`), but nothing is deployed;
  README aspirationally mentions EC2 + Vercel.
- Reverse proxy / TLS termination in front of the prod compose stack.
- Error reporting (Sentry) and metrics/tracing — only structured request logging so far.
- Broader test coverage (frontend has no tests yet; backend covers routes + cache).
- Auth — endpoints are rate-limited but unauthenticated (fine for a public demo).

---

## Running locally

```bash
docker compose up -d          # start all services (dev, hot reload)
docker compose logs backend   # watch backend logs (now includes request logs)
docker compose exec backend python -m pytest   # run the backend test suite
```

Backend hot-reloads on save (uvicorn --reload + volume mount).
Frontend hot-reloads on save (Next.js dev + volume mount).

**Production build** (no reload, multi-worker, non-root, healthchecks):

```bash
docker compose -f docker-compose.prod.yml up -d --build
```
