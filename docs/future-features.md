# Future Features — the "One-Stop F1 Platform" Roadmap

Status: **Living document** — captured 2026-07-06 from the product-vision session.
This is the reference for what PitWall AI grows into; individual features get their own
`feature-*.md` spec when work starts (see `feature-live-timing.md` for the first one).

---

## 1. The vision & the one-stop principle

**Vision:** fans come to PitWall AI and find a full-fledged system that *predicts the race*
AND *shows them everything they need to know about it* — before, during, and after every
Grand Prix. One destination, not a bookmark folder.

**The differentiator:** the official F1 app does live timing; stats sites do history —
nobody combines **prediction + explanation + live data** in one place. Our edge isn't any
single feature; it's that **the AI has an opinion about everything the fan is looking at**.
Every feature below should answer two questions: *"what's happening?"* and *"what does
PitWall AI think about it?"*

---

## 2. Feature catalogue

Effort: S (< a week) · M (1–3 weeks) · L (multi-week / new infra).
"Data" names the source we already integrate unless marked *(new)*.

### 2a. Before the race — the preview hub

| Feature | What it is | Data | Effort |
|---|---|---|---|
| **Race weekend page** | One page per GP: session schedule in the fan's timezone with countdowns, circuit guide (track outline + DRS zones, lap record, overtaking difficulty — the track agent already computes this), weather forecast, past winners. Mostly composition of existing pieces. | Ergast, OpenWeather, track agent, existing TrackMap | M |
| **Deeper predictions** | Beyond the podium: full top-10, qualifying prediction (before Saturday), sprint prediction, DNF / safety-car risk. Grid + strategy agents already produce most raw signals — mostly new synthesis prompts + response models. | Existing pipeline | M |
| **"Beat the AI" prediction league** | Fans lock podium picks before the race, get scored against the AI (grading system already exists = the game engine), leaderboards, streaks. **The retention feature** — turns visitors into weekly users. Real cost is user accounts. | Mongo + existing grading | L |

### 2b. During the race — the live command center

Extends the existing Live Race Center (`feature-live-race-center.md`). ⚠️ Verify early:
OpenF1's *true real-time* feed has access-tier restrictions; historical/near-real-time is
free. Design everything delay-tolerant (~3s+ lag).

| Feature | What it is | Data | Effort |
|---|---|---|---|
| **Live timing tower** | Leaderboard beside the track map: positions, gaps/intervals, last lap, tyre compound + stint age, pit stops. | OpenF1 `position`, `intervals`, `laps`, `stints`, `pit` | M — **spec'd in `feature-live-timing.md`** |
| **Race control feed** | Live ticker: flags, SC/VSC, penalties, investigations. Cheap to build, huge for the one-stop feeling. | OpenF1 `race_control` | S — **spec'd in `feature-live-timing.md`** |
| **Team radio player** | Playable radio clips per driver during/after a session. | OpenF1 `team_radio` | S–M |
| **Prediction vs. reality overlay** | "AI predicted VER P1 · currently P3 · prediction at risk." Join of stored prediction + live positions — a join, not a new system. The signature feature. | Mongo + live positions | S (after timing tower) |
| **AI race engineer commentary** | Short AI commentary at key moments (start, SC, pit windows, final laps) — one Haiku call per trigger event, not per lap, so cost stays sane. | Live frames + `get_llm()` | M |
| **Full race replays** | The "live" viewer is already a replay engine — lean in: replay any past race with the timing tower at 1×/2×/4×. | Existing replay backbone | S |
| **Live SSE engine** | One backend poller per live session + SSE fan-out so OpenF1 load stops scaling with viewer count. Already designed in `feature-live-race-center.md` §6 v2. | — | M–L |

### 2c. After the race — the debrief

| Feature | What it is | Data | Effort |
|---|---|---|---|
| **AI race report** | Auto-generated minutes after the flag: key moments, deciding strategy calls, winners/losers. One Sonnet call over data already fetched for grading. | Ergast + OpenF1 | S–M |
| **Prediction post-mortem** | Narrative on top of grading: "the AI missed Norris's win because practice pace was rain-masked." Transparent wrongness builds trust. | Existing grading + agents_output | S |
| **Telemetry comparisons** | Speed traces, throttle/brake, sector deltas between two drivers' laps as interactive charts. The hardcore-fan feature. | FastF1 (already wired, `asyncio.to_thread`) | M–L |
| **Strategy visualization** | Tyre-stint timeline per driver (Gantt-style), pit windows, undercut moments. | OpenF1 `stints`, `pit` | M |

### 2d. Season-level — the reference library

| Feature | What it is | Data | Effort |
|---|---|---|---|
| **AI accuracy dashboard** | Hit rate, calibration ("when the AI says 70%, is it right 70% of the time?"), per-agent contribution, per-circuit performance. Makes the predictor credible instead of a black box. | Mongo predictions | M |
| **Championship what-if calculator** | "Can Piastri still win?" — points permutations, clinch scenarios. Pure math over cached standings. | Ergast standings | S–M |
| **Head-to-head** | Teammate quali/race battles; driver vs driver at any circuit. | Ergast | M |
| **Historical archive** | Any season back to 1950, any race, any career — the Ergast service already reaches all of it. Nearly free content depth. | Ergast | M |
| **Driver & team profiles** | Career stats, current form graph, circuit affinities. ⚠️ F1 photography is licensed — stick to data + our own visuals. | Ergast | M |

### 2e. The knowledge layer

| Feature | What it is | Data | Effort |
|---|---|---|---|
| **"Ask the PitWall" chat** | Conversational agent with our existing services as tools ("Who's won the most at Monza?", "Why did Ferrari pit so early?", "Explain DRS"). The most natural extension of the agent architecture — services, LLM plumbing, and caching all exist. Also solves F1's jargon onboarding problem for new fans. | All services as LLM tools | L |
| **Rookie mode / glossary** | Explain undercut, parc fermé, delta etc. — AI explainer tooltips throughout the UI. | Static + LLM | S–M |

### 2f. Platform & retention

| Feature | What it is | Effort |
|---|---|---|
| **Accounts** | Prerequisite for the league, personalization, notifications. | L |
| **Notifications / PWA** | "Lights out in 1 hour", "AI prediction published", "Your picks scored 2/3" — what brings people back on Sunday. | M–L |
| **Personalization** | Favourite driver/team → tailored home page and highlights. | M |
| **Share cards** | Auto-generated social images of predictions ("PitWall AI says: VER P1 @ 62%") — the free marketing channel. | S–M |

---

## 3. Recommended build order

1. **Live timing tower + race control feed** — completes the Live Race Center's promise
   with data we already have; highest credibility per unit of effort.
   → **In progress: `feature-live-timing.md`.**
2. **Race weekend hub** — turns scattered pages into the "one place" the vision describes;
   mostly composition of existing pieces.
3. **Beat the AI league** (with accounts + notifications) — the retention engine;
   everything else compounds once users return weekly.
4. **AI race report + prediction post-mortem** — cheap (one LLM call per race) and
   deepens the AI identity.
5. **Ask the PitWall chat** — the flagship "wow"; save it until the data surface (1–2) is
   rich, because the chat is only as good as the tools it can call.
6. **Evergreen depth** — telemetry comparisons, what-if calculator, historical archive.

---

## 4. Constraints to keep in mind

- **OpenF1 tiers**: free tier lags ~3s and rate-limits bursts (our service already does
  backoff). True real-time may need an account/paid tier — verify before promising
  sub-second live timing.
- **Licensing**: as a free portfolio/community project on public APIs (OpenF1, Jolpica,
  FastF1) we're in normal territory. Redistributing live F1 timing *commercially* (paid
  tiers around live data) has licensing sensitivities — know where the line is first.
  Same for official photos/footage: avoid; use data and our own visuals.
- **LLM cost discipline**: any live-loop AI feature must trigger on *events* (SC, pit
  window, final laps), never per-lap/per-tick. All calls go through `agents/llm.py`
  (`get_llm` — capped tokens/timeout/retries) and expensive endpoints get
  `@limiter.limit(...)` (see CLAUDE.md).
