# Feature Spec: Live Timing Tower + Race Control Feed

Status: **Planned — next up** · Extends `feature-live-race-center.md` (its phase 6) ·
Priority #1 in `future-features.md` · Last updated: 2026-07-06

> **Why this first:** it completes the Live Race Center's promise (a track map with no
> running order is a screensaver, not a timing page) using data sources we already
> integrate, on the replay/polling backbone that already works. Highest fan credibility
> per unit of effort, and it unblocks the prediction-vs-reality overlay (the signature
> feature) as a cheap follow-up.

---

## 1. What we're building

Two new panels on `/live`, driven by the same `at` clock as the track map:

1. **Timing tower** — the running order: position, driver code, team colour, gap to
   leader, interval to the car ahead, last lap time, tyre compound + age.
2. **Race control feed** — a scrolling ticker of flags, safety car / VSC, penalties,
   and investigations.

Both work in **replay mode today** (the existing client-polling backbone) and are
designed so the future SSE live engine (`feature-live-race-center.md` §6 v2) can feed
them the exact same row shapes without frontend changes.

### Explicitly out of scope this round
- The v2 SSE poller / real live-session detection (spec §6 and phase 4–5) — the tower
  ships on v1 client polling; SSE is the round after.
- Prediction-vs-reality overlay (spec phase 7) — becomes trivial once the tower's
  running order exists; next round.
- Pit-stop column and team radio — fast follows, not needed for v1 of the tower.

---

## 2. Data (OpenF1) — what each column comes from

| Tower column | Endpoint | Notes / gotchas |
|---|---|---|
| Running order | `/position` | Rows only when a position **changes** — sparse. Current order at time `at` = each driver's **latest row ≤ `at`**. Already wrapped (`get_position`). |
| Gap to leader, interval | `/intervals` | **Race sessions only** (no gaps in practice/quali — show best lap instead). Supports `date>=`/`date<=` operator filters like `/location`; fetch a trailing window, take latest row ≤ `at` per driver. *(new wrapper)* |
| Last lap + lap number | `/laps` | ~20 × 60 ≈ 1.2k rows per race — whole-session fetch is fine. `lap_duration` is null while a lap is in progress → fall back to the previous completed lap. Already wrapped (`get_laps`). |
| Tyre compound + age | `/stints` | Stint = `compound`, `lap_start`, `lap_end`, `tyre_age_at_start`. Current stint = the one containing the driver's current lap; age = `tyre_age_at_start + (current_lap − lap_start)`. Already wrapped (`get_stints`). |
| Driver code, colour | `/drivers` | `name_acronym`, `team_colour`. Already wrapped (`get_drivers`). |
| Race control feed | `/race_control` | `date`, `category`, `flag`, `message`, `driver_number`, `lap_number`. Low volume (~hundreds of rows/race) → whole-session fetch, filter ≤ `at` in the route. *(new wrapper)* |

**Caching stance (replay-correct, live-tolerant):** replay reads historical data, so
whole-session caches are always correct there. TTLs: `intervals` 15s (windowed, like
`location`), `race_control` 60s, and **drop `get_position`'s TTL from 5 min → 60s** so a
genuinely live session isn't ordering the tower on stale data. True ~2s live freshness is
the SSE round's job, not this one's.

---

## 3. Backend

### 3a. New service wrappers (`services/openf1_service.py`)

```python
@cached(prefix="openf1:intervals", ttl=15)
async def get_intervals(self, session_key, date_gte=None, date_lte=None):
    # operator query tokens (date>=) — build query inline, same pattern as get_location

@cached(prefix="openf1:race_control", ttl=60)
async def get_race_control(self, session_key):
    return await self._get("/race_control", params={"session_key": session_key})
```

### 3b. New endpoints (`routes/live.py`)

| Endpoint | Returns |
|---|---|
| `GET /api/live/timing?session_key=&at=` | `{at, has_gaps, rows: TimingRow[]}` — assembled tower, sorted by position |
| `GET /api/live/control?session_key=&at=&limit=` | `{messages: ControlMessage[]}` — newest-first, ≤ `at`, capped (default 20, `le=50`) |

`TimingRow`: `{position, driver_number, code, team_colour, gap_to_leader, interval,
last_lap, lap_number, compound, tyre_age}` — gaps/lap as numbers or null; the frontend
formats ("+12.3", "1:23.456"). `has_gaps=false` for non-race sessions (intervals absent).

**Assembly** (in the route, one `asyncio.gather` over the cached service calls —
drivers, position, laps, stints + a trailing `intervals` window `at−120s..at`):

1. Latest position row ≤ `at` per driver → sort ascending → tower order.
2. Latest **completed** lap (`lap_duration` non-null, `date_start` ≤ `at`) per driver →
   `last_lap`, `lap_number`.
3. Stint containing `lap_number` (or the open-ended latest stint) → `compound`,
   `tyre_age`.
4. Latest interval row ≤ `at` per driver → `gap_to_leader`, `interval` (nulls early in
   a race or in practice/quali are expected — frontend shows "—").
5. Join `/drivers` for `code` + `team_colour`; drivers with no position data yet are
   omitted (session hasn't started at `at`).

The "latest row ≤ at per driver" selection is one shared pure helper
(`_latest_per_driver(rows, at, key="date")`) — unit-tested, reused by all of the above.
Pydantic response models (`TimingRow`, `ControlMessage`, …) live in a new
`models/live.py` and go on `response_model=` per CLAUDE.md.

**Validation:** `session_key: int = Query(ge=1)`, `at` parsed/validated exactly like the
existing `/api/live/map` (400 on bad timestamp). No rate limiting needed (cheap cached
reads), matching the other live endpoints.

### 3c. Tests (`backend/tests/test_live_timing.py`)

- Unit: `_latest_per_driver` (empty, out-of-order rows, rows after `at`).
- Unit: stint resolution (mid-stint age math, open-ended stint, between-stints edge).
- Route: `/timing` + `/control` with `openf1_service` monkeypatched (fixture JSON
  snippets) — assert ordering, null gaps for quali, `limit` cap, 400 on malformed `at`.

---

## 4. Frontend

### 4a. `lib/api.ts`

`TimingRow`, `TimingFrame`, `ControlMessage` interfaces + `fetchLiveTiming(sessionKey,
at, signal?)` and `fetchRaceControl(sessionKey, at, signal?)` — same shape/AbortSignal
pattern as `fetchLiveMap`.

### 4b. Components (`components/live/`)

- **`TimingTower.tsx`** — ordered rows: `P# · [team-colour bar] CODE · gap · last lap ·
  [compound pill] age`. Compound colours: soft red / medium yellow / hard white /
  inter green / wet blue. Position changes animate via CSS transform on row reorder
  (FLIP-lite: `transition` on `translateY`), matching the map's animation feel.
  Non-race sessions (`has_gaps=false`): gap column header becomes "Best lap".
- **`RaceControlFeed.tsx`** — newest-first list; flag messages get a coloured left
  border (yellow/red/green/blue per `flag`), SC/VSC highlighted. Auto-truncates to the
  `limit` from the endpoint; empty state: "No race control messages yet."

### 4c. Wiring in `LiveRaceCenter.tsx`

- New effect polling `/timing` on the same `elapsed` tick as the map (AbortController +
  stale-feed counter, identical pattern to the position poll — extract the shared
  "polled fetch" bit into a tiny hook `usePolledFetch` if it stays readable).
- `/control` polls every ~5th tick (messages are sparse; no need for 1s cadence).
- Layout (per the parent spec §7): tower replaces the current right-hand "On Track"
  aside; race control goes below the map. The aside's car list is retired (the tower
  supersedes it). Mobile: map → tower → control, stacked.

---

## 5. Task breakdown (in order)

1. **Backend wrappers + helpers** — `get_intervals`, `get_race_control`, drop
   `get_position` TTL to 60s; `_latest_per_driver` + stint helper with unit tests.
2. **Endpoints** — `models/live.py` response models; `/api/live/timing` +
   `/api/live/control`; route tests with mocked service.
3. **Frontend** — fetchers + `TimingTower` + `RaceControlFeed`; wire polling + layout
   into `LiveRaceCenter`; `docker compose exec frontend npx tsc --noEmit` clean.
4. **Verify on real data** — replay a 2024 race end-to-end: order matches reality at
   spot-checked timestamps, gaps sane, tyre ages correct across pit stops, SC messages
   appear at the right time. Also spot-check a **qualifying** session (no gaps path).
5. **Polish** — skeletons while first frame loads, stale-feed banner covers the new
   polls, mobile stacking.

## 6. Acceptance criteria

- [ ] Tower shows the correct running order at any replay timestamp, with gap/interval,
      last lap, and tyre compound + age per driver.
- [ ] Gaps gracefully absent (and column re-labelled) for practice/qualifying replays.
- [ ] Race control feed shows flags/SC/penalties in time order, capped, newest first.
- [ ] All new backend calls go through `@cached` service wrappers; endpoints have
      response models + validated params; new tests pass in CI.
- [ ] All frontend calls go through `api.ts` with AbortController; no polling pile-up at
      4× replay speed; failure surfaces via the existing stale-feed banner.
- [ ] Row shapes are frame-compatible with the future SSE engine (no frontend rework
      needed when §6 v2 lands).

## 7. Risks

- **`/intervals` availability**: race-only and occasionally sparse early in a race —
  design already treats nulls as normal ("—").
- **Position sparsity at session start**: before lights out, `/position` may only have
  grid-ordered rows; verify the first frames look sensible in step 4.
- **OpenF1 rate limits**: three more cached upstream calls per tick worst-case; the
  existing backoff + short-TTL coalescing should absorb it, but watch 429s during the
  real-data verification pass.
