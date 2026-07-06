# Feature Spec: Live Race Center (with Track Map)

Status: **In progress** — vertical slice (track map + replay) built with client polling;
next round is the timing tower + race control (see `feature-live-timing.md`), then the
live poller + SSE feed · Target phase: 6 (Flagship) · Last updated: 2026-07-06

> **Implementation status:** Phases 1–3 shipped — `openf1_service` wrappers (`/location`,
> `/position`, `session_meta`), `routes/live.py` (`/session`, `/track`, `/map`), and the
> frontend `/live` page (track map + replay clock + car dots) using **v1 client polling**.
> The **live data feed** (real live-session detection + a backend poller streaming over
> SSE) is specified in §6 and is the next round.

---

## 1. Overview

A real-time **Live Race Center** at `/live` that turns PitWall AI from a predictions
app into a destination fans open *during* a session. It shows the live running order,
a **track map with each car plotted by position**, tyre/gap data, the race-control
feed, and — the signature move — a **live "AI prediction vs reality" overlay** that
tracks how our podium call is holding up as the race unfolds.

This is the flagship feature and the highest-effort one: it introduces real-time data
plumbing the app doesn't have yet.

### The killer differentiator
Other sites show live timing. **We show live timing next to our AI's prediction**, so
fans watch the model be right or wrong in real time. That ties the prediction engine
(our core) directly to the live event.

---

## 2. Critical reality: there isn't always a live session

F1 sessions happen on race weekends only. So the feature MUST work in three states:

1. **Live** — a session is running now → poll live data.
2. **Replay / Demo** — no live session → replay a recent past `session_key` on a timer
   so the page is always demoable (essential for a portfolio project shown any day).
3. **No session** — clean empty state: "No live session. Next race in 3d 4h" + a
   "Watch a replay" button that loads the replay mode.

**Resolver priority** (`GET /api/live/session`):
1. **Live now** — a session whose start/end window contains now **and is actually
   returning data** (probe `/location` at `now − 5s`; empty ⇒ not truly live yet) →
   `mode: "live"`.
2. **Most recent completed race** → `mode: "replay"` (topical — *last weekend's* race,
   not a two-year-old one).
3. **No session** → `mode: "none"` + a "next race in Xd Yh" countdown empty state.
4. A fixed dramatic race (2024 Interlagos) only as a last-resort demo fallback /
   "watch a classic" button.

> ⚠️ **The current slice skips steps 1–3** and hard-defaults straight to the 2024 demo
> replay (for guaranteed demoability off a race weekend). That is why a 2024 race shows up
> today. Wiring real live detection + recent-race replay + the countdown state is the
> **first task of the next round** and removes that wart.

---

## 3. Scope

### In scope
- `/live` route + nav link ("Live", with a red dot when a session is active).
- **Track map** SVG plotting all cars by live x/y coordinates.
- **Timing tower**: running order, gap to leader, last lap, tyre compound + age.
- **Race control feed**: flags, safety car, investigations, penalties.
- **Prediction overlay**: current podium vs our stored prediction for this race.
- Replay mode (timer-driven playback of a past session).
- Backend proxy endpoints with short-TTL caching + a session-state resolver.

### Out of scope (future)
- Live telemetry traces (throttle/brake/speed graphs) — phase 2 of this feature.
- Driver radio audio, onboard video.
- Predictive "win probability live recompute" via the agents (expensive; later).
- Push/WebSocket transport (start with polling — see §6).

---

## 4. Data sources (OpenF1) — and the key distinction

OpenF1 is free, no API key, REST, data from 2023+. The endpoints we need (most are
**new wrappers** in `backend/services/openf1_service.py`; we already have `get_sessions`,
`get_stints`, `get_session_weather`, `get_drivers`, `get_laps`):

| Endpoint | Gives | Used for | Wrapped? |
|---|---|---|---|
| `/sessions` | session metadata, `session_key`, start/end | session-state resolver, replay picker | ✅ |
| **`/location`** | **`x, y, z` car coordinates over time** | **track map dot positions** | ❌ add |
| `/position` | classification position (P1..P20) over time | timing tower order | ❌ add |
| `/intervals` | `gap_to_leader`, `interval` (to car ahead) — **race only** | tower gaps | ❌ add |
| `/laps` | lap time, sectors | tower "last lap" | ✅ |
| `/stints` | tyre compound + lap range | tower tyre + age | ✅ |
| `/drivers` | number → name, team, **team_colour** | labels, car colours | ✅ |
| `/race_control` | flags, SC/VSC, messages | race-control feed | ❌ add |
| `/car_data` | speed, throttle, brake, drs, gear, rpm | (phase 2 telemetry) | ❌ add later |

> ⚠️ **`/location` vs `/position` is the #1 gotcha.** `/location` returns spatial
> `x, y, z` coordinates (in ~1/10 m units) — that's what plots a car on the map.
> `/position` returns the *ranking* (1st, 2nd…), not coordinates. We need BOTH:
> `/location` for the map, `/position` for the tower order.

> ⚠️ **Two hard-won rules for `/location` (verified):**
> 1. **Never fetch a whole session** — it's ~35k rows and an unfiltered live query
>    **404s**. Always pass a time window (`date>=`/`date<=`); a 2–4s window returns all
>    cars' latest samples in a tiny payload.
> 2. **For live, query `now − ~5s`, not `now`.** OpenF1's free tier lags ~3s, so a query at
>    exactly "now" returns nothing. A ~5s safety margin is the difference between an empty
>    map and a working one. (This also explains the live-session `/location` 404 we saw.)

### Drawing the track outline
OpenF1 gives car coordinates but **not** a track shape. Derive the outline once per
circuit by taking the `/location` points of a single driver across one full clean lap
and tracing the path as an SVG `<polyline>`. Normalize all `x/y` by the circuit's
min/max bounds into the SVG viewBox. Cache the computed outline (it's static per
circuit) — e.g. a `circuit_outline:{session_key}` cache key or a committed JSON.

---

## 5. New backend endpoints

All under a new `backend/routes/live.py` (`APIRouter(prefix="/api/live")`), mounted in
`main.py`. These **proxy OpenF1**, normalize the payload, and cache briefly so we don't
hammer OpenF1 and so the browser gets a small, clean shape.

| Endpoint | Returns | Cache TTL |
|---|---|---|
| `GET /api/live/session` | current state: `{mode: "live"|"replay"|"none", session_key, meeting_name, circuit_id}` | 30s |
| `GET /api/live/map?session_key=&at=` | per-driver `{num, name, colour, x, y}` normalized to viewBox, at timestamp `at` | 2s (live) |
| `GET /api/live/timing?session_key=&at=` | tower rows: `{pos, num, name, colour, gap, last_lap, compound, tyre_age}` | 2s |
| `GET /api/live/control?session_key=&since=` | race-control messages since cursor | 5s |
| `GET /api/live/track?session_key=` | precomputed SVG outline points for the circuit | 1 day |
| `GET /api/live/overlay?session_key=` | `{prediction: {...stored...}, current_top3: [...]}` for the vs-reality panel | 5s |
| **`GET /api/live/stream?session_key=`** *(live path, §6 v2)* | **SSE** — pushes a combined `frame` (cars + order + gaps + control) every ~1–2s from a single backend poller | n/a (stream) |

Notes:
- **Short-TTL caching**: the existing `@cached` decorator takes a `ttl` — use 2–5s for
  live endpoints. (≈ a NestJS interceptor cache with a tiny TTL.) This both rate-limits
  OpenF1 and lets many viewers share one upstream fetch.
- **Replay mode**: the client passes an `at` timestamp that advances on a timer; the
  backend filters OpenF1 rows to `<= at`. This makes "replay" just "live with a fake
  clock," so the same endpoints serve both modes. The session resolver returns the
  replay `session_key` + the session's start time so the client can compute `at`.
- **Overlay**: join the live top-3 (from `/position`) against the stored prediction in
  Mongo (`predictions` collection, matched by race/year) → who we called vs who's there.

Add typed fetchers + interfaces to `frontend/src/lib/api.ts` for each.

---

## 6. Live update architecture (constant data feed → frontend)

OpenF1 has **no push** — it must be polled. The design has **two independent sides**: how
the **backend pulls** from OpenF1, and how the **browser receives** updates from us. Get
these right separately.

### The rule that makes live work: query `now − ~5s`
Live queries must hit a **small time window ending at `now − ~5s`** (see §4). Querying at
"now" returns nothing (OpenF1 lags ~3s) and unfiltered whole-session queries 404. Replay
uses the same window, driven by a fake clock instead of `now`.

### v1 — client polling (what the slice ships today)
The `/live` page polls `/api/live/map?at=` (~1s) and later `/timing`, `/control`; the
backend queries a windowed `/location` per request; a short-TTL Redis cache coalesces
concurrent viewers. Cars interpolate between frames via a CSS transition.
- ✅ Simple, stateless backend — perfect for **replay** (not latency-sensitive).
- ⚠️ Every viewer runs its own polling loop and drives its own upstream work; OpenF1 load
  and latency **scale with viewer count**. Fine at small scale, not a live crowd.

### v2 — one backend poller + SSE fan-out (the live engine)
For genuine live sessions, **decouple the OpenF1 fetch rate from the number of viewers**:

```
OpenF1  ──poll ~1–2s (at = now−5s)──►  ┌──────────────────────────┐
(windowed /location,/position,          │  Session Poller (1 task) │
 /intervals,/race_control)              │  assembles one "frame":  │
                                        │  cars x/y + order + gaps │
                                        │  + latest control msgs   │
                                        └────────────┬─────────────┘
                                                     │ publish frame
                                    ┌────────────────┼────────────────┐
                                 SSE│             SSE│             SSE│
                                ┌───▼────┐      ┌───▼────┐      ┌───▼────┐
                                │browserA│      │browserB│      │browserC│
                                └────────┘      └────────┘      └────────┘
```

- **One** async task per live session polls OpenF1 every ~1–2s at `at = now − 5s` and
  assembles a compact **frame** (all cars' x/y + running order + gaps + latest
  race-control messages).
- It **publishes each frame over SSE** (`text/event-stream`, consumed with `EventSource` —
  the same transport as the prediction stream we already built). Browsers hold **one open
  stream** and stop polling; they interpolate dot movement between frames.

**Why this shape**
- **1 upstream poll serves N viewers** — OpenF1 rate-limit exposure stops scaling with
  traffic (the main win).
- **Lower, steadier latency** — push the instant a frame is ready, no client poll interval
  stacked on top.
- **SSE, not WebSocket** — we only need server→client; SSE also auto-reconnects for free.
  WebSocket's bidirectional complexity buys us nothing here.

**Details that make or break it**
- **Poller lifecycle:** start the task on first viewer, stop after the last disconnects (or
  run it for the live session's duration). **Guard against duplicate pollers** for the same
  session (a module-level registry keyed by `session_key`).
- **Single vs multi-process:** the backend runs one uvicorn process today, so an
  **in-memory `asyncio` broadcast** (e.g. a set of per-connection queues) is enough now.
  With multiple workers, switch to **Redis pub/sub** — the poller publishes frames to a
  Redis channel; each worker's SSE handler subscribes. Build the seam even if we start
  in-memory.
- **On connect, send the latest frame immediately** so a new viewer isn't staring at a
  blank track until the next poll.
- **Unify replay + live:** it's the *same* stream — live drives `at = now − 5s`, replay
  drives `at = fakeClock`. Replay is "live with a fake clock," so we never build two
  systems; the frontend consumes one SSE feed either way.

### v3 (later)
WebSocket only if we ever add client→server interaction (we don't). Optional background
ingest of a session into Redis/Mongo as a time-series buffer if we want scrubbing/rewind.

**Decision:** keep **client polling for replay** (simple, latency-insensitive); add the
**poller + SSE** path for genuine live sessions. Only the live path needs new infra — the
map, coordinate normalization, and dot interpolation are unchanged.

---

## 7. Frontend

**Route**: `app/live/page.tsx` (client component — it polls + animates).

**Components** (`components/live/`):
- `LiveRaceCenter.tsx` — page shell; resolves session state, owns the replay clock.
- `TrackMap.tsx` — SVG: draws the cached outline `<polyline>` + a `<circle>` per car at
  normalized `x/y`, coloured by `team_colour`, labelled with driver code. Animate dot
  movement with a CSS/Framer transition between polls so motion looks smooth.
- `TimingTower.tsx` — ordered list of driver rows (pos, name, gap, last lap, tyre).
- `RaceControlFeed.tsx` — scrolling list of flag/SC/penalty messages.
- `PredictionVsReality.tsx` — two columns: "AI predicted" podium vs "Currently" top-3,
  with ✓/✗ per slot (reuse styling from `PredictSheet`'s `ActualResultComparison`).
- `SessionStateBanner.tsx` — LIVE / REPLAY / countdown empty state.

**Layout**
```
┌───────────────────────────────────────────────┬─────────────────┐
│                                                │  TIMING TOWER   │
│              TRACK MAP (SVG)                    │  P1 ...         │
│        cars plotted by live x/y                 │  P2 ...         │
│                                                │  ...            │
├───────────────────────────────────────────────┼─────────────────┤
│  PREDICTION vs REALITY (AI podium ↔ live top3) │ RACE CONTROL    │
└───────────────────────────────────────────────┴─────────────────┘
   [ LIVE ● ]  or  [ REPLAY ▶ 2024 Monaco ]  banner on top
```

**Nav**: add `{ href: "/live", label: "Live" }` to `NAV_LINKS` in `MainNav.tsx`, with a
red pulse dot when `mode === "live"`.

> Per `frontend/AGENTS.md`, this is a modified Next.js — check `node_modules/next/dist/docs/`
> before using App Router / data APIs. shadcn/ui for primitives; Framer Motion for dot
> animation (named in initial scope).

---

## 8. Phased plan

1. ✅ **Session resolver + replay backbone** — `openf1_service` wrappers (`/location`,
   `/position`, `session_meta`); `routes/live.py` with `/session` + the replay clock.
2. ✅ **Track outline + map** — `/api/live/track` computes the outline; `TrackMap` renders
   outline + cars (normalized, Y-flipped).
3. ✅ **Make it move** — replay clock + `/api/live/map?at=` client polling; cars animate.
4. **Real live detection** *(next)* — upgrade `/session` to the §2 resolver priority: live
   now (probed at `now − 5s`) → recent completed race → countdown empty state → demo
   fallback. Removes the "2024 shows up" wart.
5. **Live data feed** *(next)* — the §6 v2 engine: a single backend **session poller** at
   `now − 5s` + **SSE fan-out** (`/api/live/stream`), in-memory broadcast now with a Redis
   pub/sub seam. Frontend consumes one SSE feed for both live and replay.
6. **Timing tower + race control** — `/timing` + `/control` endpoints and components.
   → **Spec'd and prioritized next: see `feature-live-timing.md`** (ships on the v1
   polling backbone; deliberately sequenced before phases 4–5).
7. **Prediction vs reality overlay** — join live top-3 with the stored prediction.
8. **States & polish** — live/replay/empty states, nav red-dot, mobile fallback, skeletons.
9. **(Later)** live telemetry traces; optional time-series ingest for scrubbing.

---

## 9. Risks & open questions
- **Coordinate normalization**: `/location` units/orientation vary per circuit; must
  fit to viewBox via per-session min/max bounds, and may need axis flip. Validate on 2–3
  circuits.
- **OpenF1 rate limits / latency**: free tier has ~3s delay; short-TTL backend cache +
  shared upstream fetch mitigates. Confirm acceptable poll cadence.
- **Replay realism**: pick a dramatic past race (e.g. a wet/SC race) for the demo so the
  feature shines.
- **Map performance**: 20 dots @ 2s polling is cheap; smooth animation is the only perf
  concern — interpolate between polls rather than re-poll faster.
- **Open**: do we want replay speed control (1×/2×/4×)? (Default: 1× with a 2× toggle.)
- **Open**: persist computed circuit outlines as committed JSON vs recompute+cache?
  (Default: cache in Redis keyed by circuit; promote to committed JSON if it's flaky.)

## 10. Acceptance criteria
- [ ] `/live` correctly resolves and shows LIVE, REPLAY, or empty state.
- [ ] Track map draws the circuit outline and plots all running cars by `/location`
      x/y, coloured per team, updating on the poll interval.
- [ ] Timing tower shows correct running order with gap, last lap, and tyre.
- [ ] Race-control feed streams flags/SC/penalty messages.
- [ ] Prediction-vs-reality panel shows our stored podium beside the live top-3 with
      ✓/✗ per position.
- [ ] Replay mode plays a past session end-to-end on a timer with no live session.
- [ ] All backend live endpoints cached with short TTL; all frontend calls via `api.ts`.
