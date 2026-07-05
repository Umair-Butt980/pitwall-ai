# Architecture — PitWall AI

Status: **Current** · Last updated: 2026-07-05

A complete map of how PitWall AI is built: the system layers, the multi-agent
prediction pipeline, how the agents communicate, and how a prediction flows from a click
to a podium. For *planned* changes (accuracy fixes, dependency edges) see
[`feature-agent-transparency-and-accuracy.md`](./feature-agent-transparency-and-accuracy.md).

---

## 1. System overview

PitWall AI is a **modular monolith**: a Next.js frontend talks to a FastAPI backend, which
orchestrates seven LangGraph agents (backed by Claude) to produce a P1/P2/P3 podium
prediction, then grades those predictions against real results.

```
┌──────────────┐     HTTPS/SSE      ┌────────────────────────────────────────┐
│   Browser    │ ─────────────────► │              FastAPI backend           │
│ Next.js app  │ ◄───────────────── │                                        │
│ (App Router) │   JSON / event-    │  routes → services → agents (LangGraph)│
└──────────────┘   stream           │            │            │              │
                                    │            ▼            ▼              │
                                    │       ┌─────────┐  ┌──────────┐        │
                                    │       │  Redis  │  │ MongoDB  │        │
                                    │       │ (cache) │  │ (preds)  │        │
                                    │       └─────────┘  └──────────┘        │
                                    └──────────┬─────────────┬───────────────┘
                                               │             │
                             external data ◄───┘             └───► Anthropic API
                     (Jolpica/Ergast, OpenF1, OpenWeather, FastF1)   (Claude LLMs)
```

**Tech stack**
- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind, shadcn/ui, dark F1 theme.
- **Backend:** Python 3.12, FastAPI, LangGraph (agent orchestration), LangChain +
  `langchain-anthropic` (Claude), pydantic-settings.
- **Data stores:** MongoDB (stored predictions + grading), Redis (transparent API cache).
- **Runtime:** Docker Compose (`backend` :8000, `frontend` :3000, `redis`, plus Mongo).
  Both app containers hot-reload from a source volume mount.

---

## 2. Backend layers

```
backend/
  main.py            FastAPI app — lifespan (opens/closes pooled clients), router mounts
  config.py          get_settings() singleton — all env vars (pydantic-settings)
  database/
    connection.py    Connections: one pooled httpx client + Mongo + Redis, shared app-wide
  services/          One class per external API; each method @cached(prefix, ttl) in Redis
    base.py          BaseHTTPService._get() over the shared httpx client
    cache.py         @cached decorator — read/write Redis, degrade to pass-through if down
    ergast_service.py    Jolpica/Ergast — schedule, results, standings, qualifying/sprint
    openf1_service.py    OpenF1 — sessions, laps, stints, drivers, session_result, grid
    weather_service.py   OpenWeatherMap — race-day forecast
    fastf1_service.py    FastF1 (SYNC lib → always asyncio.to_thread) — session results
  agents/            The LangGraph pipeline (see §3)
  models/
    prediction.py    Pydantic schemas: per-agent outputs + final PredictionOutput
    race.py          Race/standings response models
  routes/
    health.py        GET /health
    races.py         GET /api/races, circuit history, race result
    drivers.py       GET /api/drivers/{id}/stats/{circuit}
    predictions.py   POST /predict, GET /predict/stream (SSE), /history, /stats
```

**Cross-cutting patterns**
- **Caching:** every external call is wrapped in `@cached(prefix, ttl)`. Redis is
  best-effort — if it's down the call still runs (no hard dependency). TTLs reflect data
  volatility: OpenF1 ~5 min (live), OpenWeather ~1 h, Ergast standings ~6 h, FastF1 ~1 wk.
- **Shared clients:** a single pooled `httpx.AsyncClient`, one Mongo client, one Redis
  client — created in the app lifespan, reused everywhere (no per-request pools).
- **Service singletons:** each service is instantiated at module bottom
  (`openf1_service = OpenF1Service()`); callers import the instance.
- **FastF1 is synchronous** and always run off-thread via `asyncio.to_thread`.

---

## 3. The prediction pipeline (LangGraph)

### 3.1 Topology — fan-out / fan-in

Seven analysis agents run **in parallel** from `START` (one LangGraph superstep). When all
seven complete, the **synthesis** node fires (automatic fan-in), then `END`.

```
                 ┌──► weather  ──┐
                 ├──► driver   ──┤
                 ├──► car      ──┤
        START ──►├──► track    ──┼──► prediction ──► END
                 ├──► strategy ──┤     (synthesis,
                 ├──► practice ──┤      Claude Sonnet)
                 └──► grid     ──┘
```

Defined in `agents/orchestrator.py`: nodes are registered, then for each analysis node an
edge `START → node` (fan-out) and `node → prediction` (fan-in) is added. The graph is
compiled **once at import** (`prediction_graph = build_graph()`) and is stateless, so it's
safe to share across concurrent requests.

### 3.2 How the agents communicate — shared state, not peer-to-peer

This is the key design point: **the analysis agents do not talk to each other.** They
communicate through a shared `PredictionState` (`agents/state.py`, a `TypedDict`) — think
of it as a request-scoped context object:

- The **route** fills the read-only inputs once: `race_name`, `year`, `circuit_id`,
  `lat`/`lon`, and the current-season `driver_standings` + `constructor_standings`.
- Each analysis node **reads** those shared inputs and **writes only its own slice**
  (`weather_output`, `grid_output`, …). Because they run in the same parallel superstep,
  no agent can see another agent's output — they're independent extractors.
- LangGraph merges each node's partial dict back into the shared state automatically.
- The **synthesis node** (`prediction`) runs last and reads **all seven** outputs plus the
  standings, and does the cross-domain reasoning that combines them.

So "combining signals" happens in exactly one place — the synthesizer — not by chaining
agents. This keeps the analysis agents simple and independent, and avoids one agent's
error propagating into another. (A small number of *genuine* dependencies — e.g. Strategy
needing the weather — are a planned refinement; see §7 and the accuracy spec.)

### 3.3 The agents

Six analysis agents use **Claude Haiku 4.5** (fast, cheap, sufficient for structured
extraction); the synthesizer uses **Claude Sonnet** (stronger cross-domain reasoning).
Each agent uses `ChatAnthropic(...).with_structured_output(<PydanticModel>)`, so Claude is
forced to return a validated object.

| Agent | File | Real data source | Output model | Grounding |
|---|---|---|---|---|
| **Grid & Sprint** | `grid_agent.py` | OpenF1 `session_result` + `starting_grid` (this weekend's qualifying + sprint) | `GridAnalysis` | **Fully computed** — grid/positions are facts; LLM only writes `notes` |
| **Practice** | `practice_agent.py` | OpenF1 `laps` for FP1–FP3 | `PracticeAnalysis` | **Fully computed** — best-lap & long-run pace ranked in Python |
| **Weather** | `weather_agent.py` | OpenWeatherMap forecast at race lat/lon | `WeatherAnalysis` | Real forecast (falls back to climate knowledge if key/coords missing) |
| **Driver** | `driver_agent.py` | Ergast circuit history + standings + last-year qualifying | `DriverAnalysis` | Partly grounded — some per-driver numbers are LLM-estimated |
| **Car** | `car_agent.py` | Last-year race (FastF1) + constructor standings | `CarAnalysis` | Partly grounded — reliability/perf partly LLM-estimated |
| **Track** | `track_agent.py` | Ergast recent winners (context only) | `TrackAnalysis` | LLM general knowledge (no measured telemetry) |
| **Strategy** | `strategy_agent.py` | OpenF1 stints from last year's race | `StrategyAnalysis` | Real stint data; pit windows LLM-estimated; **not weather-aware** |
| **Synthesis** | `prediction_agent.py` | All seven outputs + live standings | `PredictionOutput` | Sonnet weighs signals into the final podium |

**Signal-weighting philosophy** (encoded in the synthesis prompt, strongest first):
1. **Qualifying grid** (when available) — the single best predictor for *this* race.
2. **Current championship standings** — who's performing *now* (beats historical dominance).
3. **Practice pace / sprint result** — freshest form; can move drivers off the pure order.
4. Weather, car, track, strategy as modifiers. Wet weather discounts the grid.

The synthesizer must return an exactly-3 podium (`winner == podium[0]`), a confidence, a
reasoning paragraph, an alternative-scenario, and `driver_probabilities` for the top 8.

---

## 4. Data sources

| Source | Base URL | Used for | Notes |
|---|---|---|---|
| **Jolpica / Ergast** | `api.jolpi.ca/ergast/f1` | Schedule, results, standings, circuit history, race grading | Maintained Ergast successor |
| **OpenF1** | `api.openf1.org/v1` | Live sessions, laps, stints, qualifying grid, sprint results | Rate-limits under bursts → OpenF1 service retries with backoff on 429 |
| **OpenWeatherMap** | `api.openweathermap.org/data/2.5` | Race-day forecast (temp, conditions, rain %) | Needs `OPENWEATHERMAP_API_KEY` |
| **FastF1** | (library + on-disk cache) | Last-year session classification | Synchronous → `asyncio.to_thread` |
| **Anthropic** | Claude API | All agent reasoning | Haiku (analysis) + Sonnet (synthesis) |

---

## 5. Request lifecycle — predictions

There are two entry points, both in `routes/predictions.py`; they share
`_prepare_prediction()` (resolves circuit metadata + standings, builds the initial state).

**A. Blocking — `POST /api/predictions/predict`**
1. Resolve the race from the season schedule (404 if the name doesn't match).
2. Fetch driver + constructor standings once (shared via state).
3. `await prediction_graph.ainvoke(initial_state)` — blocks ~15–40 s until the whole graph
   completes.
4. Persist the prediction + all agent outputs to MongoDB (async, non-blocking).
5. Return the final `PredictionOutput`.

**B. Streaming — `GET /api/predictions/predict/stream` (Server-Sent Events)**
1–2. Same setup.
3. `prediction_graph.astream(initial_state, stream_mode="updates")` yields each node's
   output **the moment it completes**. Each analysis agent → one SSE `data:` frame in real
   completion order; the synthesis node → a terminal frame carrying the podium.
4. Persist after the stream ends.
- The browser consumes this via `EventSource` (`streamPrediction()` in `lib/api.ts`), so
  the predict sheet reveals each agent's real findings live instead of on fake timers.

**Persistence & grading**
- Every prediction is stored with `round` + `race_date` and the full `agents_output`.
- `_grade_pending_predictions()` (lazy, on `/history` and `/stats`) finds ungraded
  predictions whose race has passed, fetches the real podium, and records `actual_winner`,
  `was_correct`, and `podium_correct_count` — each item graded independently so one failure
  can't break the batch.
- `GET /api/predictions/stats` aggregates the graded set into winner accuracy + average
  podium hits (+ per-circuit breakdown) for the dashboard scorecard.

---

## 6. Frontend architecture

```
frontend/src/
  app/
    layout.tsx        Root layout — sticky MainNav, dark theme, fonts
    page.tsx          Dashboard grid (server component): next race + championship + AI scorecard
    standings/        Driver + constructor standings tabs
    drivers/[id]/     Driver circuit stats
    history/          Prediction history (predicted vs actual)
  components/
    PredictSheet.tsx      Core UX — subscribes to the SSE stream, shows each agent's live
                          result in expandable cards, then the podium + win-prob bars
    AgentStatusRow.tsx    One agent row: pending / analysing / done, expandable detail panel
    RaceCard, NextRaceHero, CircuitHistoryPanel, dashboard/* widgets
  lib/
    api.ts            ALL backend calls + typed models; streamPrediction() (EventSource)
```

**Conventions**
- **Every** backend call goes through `lib/api.ts` — pages/components never `fetch` directly.
- Pages needing async data are **server components**; anything with state/effects/browser
  APIs (`PredictSheet`, `AgentStatusRow`, `MainNav`, …) is a **client component**.
- Dark mode is locked; F1 red primary lives in `globals.css`. shadcn/ui only.

---

## 7. Grounding & anti-hallucination design

The system fights the LLM's training-cutoff bias (predicting perennial winners) with layered
grounding:
- **Live standings** injected into state so agents score current form, not reputation.
- **Grid + practice agents** compute from real timing data — the LLM only narrates facts.
- **Synthesis prompt** explicitly ranks grid > standings > practice > history.

Two known gaps remain (tracked in the accuracy spec, not yet fixed):
- **Type A — invented data:** Driver/Car agents still LLM-estimate some numbers we could
  compute. Fix = route real data in.
- **Type B — wrong-world reasoning:** Strategy has no weather input, so it can produce
  dry-race strategy for a wet race. Fix = add a `weather → strategy` (and `track →
  strategy`) dependency edge so those agents run after the facts they need.

Accuracy is measured, not assumed: every change is validated by grading real races
(`/stats`). Realistic target is **podium hit-rate ~70–85%**; exact-winner in F1 tops out
~45–55%.

---

## 8. Environment & running

```bash
docker compose up -d          # start backend, frontend, redis (+ mongo)
docker compose logs backend   # watch backend logs
docker compose exec backend python -c "..."   # run a script in app context
```

Required env (via `.env`, read by `config.py`):
`ANTHROPIC_API_KEY`, `OPENWEATHERMAP_API_KEY`, plus Mongo/Redis connection settings.
Both containers hot-reload on save. Adding a Python dep requires
`docker compose build backend` (deps install at image build, not from the volume mount).

---

## 9. Related docs
- [`feature-grid-sprint-agent.md`](./feature-grid-sprint-agent.md) — the Grid & Sprint agent.
- [`feature-agent-transparency-and-accuracy.md`](./feature-agent-transparency-and-accuracy.md)
  — SSE streaming + the accuracy/hallucination roadmap.
- [`feature-dashboard-redesign.md`](./feature-dashboard-redesign.md) — dashboard landing.
- [`initialScope.md`](./initialScope.md) — original project scope.
