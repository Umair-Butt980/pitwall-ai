# Feature Spec: Dashboard Landing Redesign

Status: **Planned** · Owner: TBD · Target phase: 5 (Polish) · Last updated: 2026-06-30

---

## 1. Overview

Today the home page (`frontend/src/app/page.tsx`) is a `NextRaceHero` + a flat grid of
`RaceCard`s. It works, but it reads as "a race list," not "mission control." This
feature turns the landing page into a **dashboard** — a single screen that answers, at
a glance: *What's next? Who's leading? How is the AI doing? What's the latest call?*

Goal: when an F1 fan lands on PitWall AI, the homepage should feel like an analysis
command center, not a calendar.

### Success looks like
- A fan understands the current state of the championship + next race in < 5 seconds.
- The AI's credibility is visible up front (accuracy stat), encouraging trust.
- Every tile is a launchpad into a deeper page (standings, prediction, history).

---

## 2. Scope

### In scope
- New dashboard layout for `/` composed of modular "widget" cards.
- Reuse of existing data (races, standings, prediction history) — **no new agents**.
- One small new backend aggregate endpoint for headline stats (optional, see §5).
- Responsive grid (mobile → desktop), dark F1 theme, skeleton loading states.

### Out of scope (later / separate docs)
- Live timing / track map → see `feature-live-race-center.md`.
- User accounts, favorites, personalization (future).
- New charts requiring data we don't already expose.

---

## 3. Dashboard widgets (the grid)

A responsive bento-style grid. Each widget is a self-contained component that fetches
its own data and renders a skeleton while loading (matches the current `page.tsx`
pattern).

| Widget | Content | Data source (existing) | Links to |
|---|---|---|---|
| **Next Race Hero** (full-width) | Keep current `NextRaceHero` — countdown, circuit, date. Add a "Predict this race" CTA. | `fetchRaces` | opens `PredictSheet` |
| **Championship Pulse** | Top 3 drivers + top 3 constructors with points + gap-to-leader. | `fetchDriverStandings`, `fetchConstructorStandings` | `/standings` |
| **AI Scorecard** | Headline accuracy: winner hit-rate %, avg podium hits /3, # predictions graded. | `fetchPredictionHistory` (compute client-side) or new `/api/predictions/stats` | `/history` |
| **Latest Prediction** | Most recent prediction: podium + confidence + correct/✗ badge if graded. | `fetchPredictionHistory[0]` | `/history` |
| **Season Progress** | "Round 11 / 24" with a progress bar; next 3 upcoming races as mini-rows. | `fetchRaces` | `/` calendar |
| **Form Movers** (optional) | Biggest standings climbers/fallers over last race (needs prev-round delta). | derived from standings + recent results | `/standings` |

Below the grid: keep the **full race calendar** (`RaceCard` grid) as a "Full Calendar"
section so nothing is lost — just demoted below the dashboard widgets.

---

## 4. UX / layout

```
┌─────────────────────────────────────────────────────────┐
│  NEXT RACE HERO  (countdown · circuit · [Predict] CTA)   │  full width
├──────────────────────┬──────────────────┬───────────────┤
│  Championship Pulse  │   AI Scorecard   │  Latest       │
│  (drivers + teams)   │  (accuracy %)    │  Prediction   │
├──────────────────────┴──────────────────┴───────────────┤
│  Season Progress  (Round X/24 + next 3 races)            │
├─────────────────────────────────────────────────────────┤
│  FULL CALENDAR  (existing RaceCard grid)                 │
└─────────────────────────────────────────────────────────┘
```

- Grid: `grid-cols-1 lg:grid-cols-3` for the widget row, `max-w-7xl mx-auto px-4 sm:px-6`.
- Cards: shadcn `Card`; keep dark theme + F1-red accent (`--primary`).
- Each numeric stat gets a label in `text-xs uppercase tracking-widest text-muted-foreground`
  (matches existing section headers).
- Charts (gap-to-leader sparkline, accuracy donut) use **Recharts** (already in the
  intended stack per `docs/initialScope.md`) — add it if not yet installed.

---

## 5. Backend (optional, recommended)

Most widgets can be computed client-side from endpoints we already have. To keep the
dashboard fast and avoid shipping the full history to the browser, add ONE aggregate
endpoint:

**`GET /api/predictions/stats`** → in `backend/routes/predictions.py`
```jsonc
{
  "total": 12,            // predictions made
  "graded": 8,            // races that have run
  "winner_correct": 5,    // predicted winner == actual winner
  "winner_accuracy": 0.625,
  "avg_podium_hits": 1.9, // mean of podium_correct_count over graded
  "by_circuit": [ { "circuit_id": "monaco", "winner_correct": 1, "graded": 1 } ]
}
```
- Computed with a Mongo aggregation over the `predictions` collection (the grading
  fields `was_correct`, `podium_correct_count` already exist).
- Cache with the existing `@cached` decorator (e.g. `ttl=300`).
- ≈ a NestJS controller method returning a computed DTO — pure read, no agents.

Add a typed `fetchPredictionStats()` to `frontend/src/lib/api.ts` (all calls go through
`api.ts` per project convention).

---

## 6. Files to add / change

**Frontend**
- `app/page.tsx` — recompose into the dashboard layout (orchestrates widgets).
- `components/dashboard/ChampionshipPulse.tsx` — new.
- `components/dashboard/AiScorecard.tsx` — new.
- `components/dashboard/LatestPrediction.tsx` — new.
- `components/dashboard/SeasonProgress.tsx` — new.
- `components/dashboard/DashboardSkeleton.tsx` — new (compose existing `Skeleton`).
- `lib/api.ts` — add `fetchPredictionStats()` + types.
- Possibly `npx shadcn add card progress` (via `docker compose exec frontend ...`).

**Backend**
- `routes/predictions.py` — add `GET /api/predictions/stats`.

> Note: per `frontend/AGENTS.md` this is a **modified Next.js** — read the relevant
> guide under `node_modules/next/dist/docs/` before using any App Router APIs.

---

## 7. Phased plan

1. **Backend stats endpoint** — add `/api/predictions/stats` + cache + `api.ts` fetcher.
   Verify with `curl localhost:8000/api/predictions/stats`.
2. **Static widget shells** — build the 4 new widgets with skeletons + dummy data,
   lay out the grid in `page.tsx`. Confirm responsive behaviour.
3. **Wire real data** — connect each widget to its fetcher; loading + empty states.
4. **Charts & polish** — add Recharts sparkline/donut, F1-red accents, hover states.
5. **QA** — empty-state (no predictions yet), mobile, dark-theme contrast.

---

## 8. Acceptance criteria
- [ ] `/` renders the widget grid above the full calendar, fully responsive.
- [ ] AI Scorecard shows real winner-accuracy from graded predictions (or a clean
      "No graded predictions yet" empty state).
- [ ] Championship Pulse shows current top-3 drivers + constructors with gaps.
- [ ] Latest Prediction shows the most recent podium + confidence + graded badge.
- [ ] Every widget links to its deeper page; all skeletons render during load.
- [ ] No direct `fetch` in components — all calls go through `lib/api.ts`.

## 9. Open questions
- Do we want the AI Scorecard accuracy to be **all-time** or **last-N races**? (Default: all-time, with a small "last 5" toggle later.)
- Recharts vs a lighter option (the initial scope names Recharts — default to it).
