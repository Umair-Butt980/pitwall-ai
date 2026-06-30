# Feature Spec: Live Race Center (with Track Map)

Status: **Planned** · Owner: TBD · Target phase: 6 (Flagship) · Last updated: 2026-06-30

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

Detecting state: query OpenF1 `/sessions` for today; if a session's start/end window
contains "now", it's live. Otherwise pick the most recent finished session for replay.

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

## 6. Real-time transport: start simple

OpenF1 has **no push** — it's polled. So:

- **v1 (recommended): client polling.** The `/live` page polls the backend endpoints on
  intervals (map/timing ~2s, control ~5s) using `setInterval` or SWR's `refreshInterval`.
  Backend short-TTL cache coalesces load. Simple, robust, good enough.
- **v2 (later): SSE.** A backend `text/event-stream` that pushes deltas, so the browser
  stops polling. Nice-to-have; not needed for the first cut.
- WebSockets are overkill here (no client→server messaging needed).

Decision: **build v1 polling first.** Note it in code so v2 SSE is an easy swap.

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

1. **Session resolver + replay backbone** — `openf1_service` wrappers for `/location`,
   `/position`, `/intervals`, `/race_control`; `routes/live.py` with `/session` and the
   replay clock concept. Verify with `curl` against a known past `session_key`.
2. **Track outline + static map** — `/api/live/track` computes the outline; `TrackMap`
   renders the outline + cars at a single frozen timestamp (no polling yet).
3. **Make it move** — add the replay clock + polling; cars animate between frames.
4. **Timing tower + race control** — `/timing` + `/control` endpoints and components.
5. **Prediction vs reality overlay** — join live top-3 with stored prediction.
6. **States & polish** — live/replay/empty states, nav red-dot, mobile fallback
   (map scrolls; tower stacks below), loading skeletons.
7. **(Optional v2)** SSE transport; live telemetry traces.

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
