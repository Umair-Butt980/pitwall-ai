# Feature Spec: Agent Transparency & Accuracy Improvements

Status: **Planned** · Owner: TBD · Target phase: 5 (Accuracy) · Last updated: 2026-07-04

---

## 1. Overview

Two related weaknesses surfaced while shipping the Grid & Sprint agent:

1. **The multi-agent work is invisible.** The frontend fakes agent progress and the
   backend throws the agent detail away — so users never see *why* a prediction was made.
2. **Some agents hallucinate.** A few produce confident output that is either invented
   or based on the wrong scenario, which then poisons the final synthesis.

This spec documents both problems precisely and the proposed fixes, so the work can be
done in measured passes rather than guessed at.

### Success looks like
- Each agent's *real* findings are shown to the user as they complete.
- The two classes of hallucination below are eliminated at the source.
- Every accuracy change is validated by back-testing, not by vibes.

---

## 2. Problem A — Agent results are invisible / faked

### Current behaviour
- `POST /api/predictions/predict` (`backend/routes/predictions.py`) runs the LangGraph
  pipeline as a single blocking call (15–40s) and returns **only** the final
  `PredictionOutput`. The rich per-agent output (`agents_output`) is saved to MongoDB but
  **never sent to the browser**.
- `frontend/src/components/PredictSheet.tsx` lights up its agent rows on **fixed 1.2s
  timers** that have nothing to do with real agent completion. The rows are cosmetic; the
  real findings (grid order, sprint result, practice ranks, analyst notes) are discarded.

### Why it matters
The core product story is "7 specialist agents analyse the race." Today that story is a
UI animation, not the truth. Showing the real analysis builds trust and makes the
prediction explainable ("Leclerc dropped off the podium because he faded in the sprint").

### Proposed solution
- **Stream real completion via SSE.** Use LangGraph's `graph.astream(state,
  stream_mode="updates")` to yield each node's output the moment it completes. Expose a
  streaming endpoint (`text/event-stream`) via FastAPI `StreamingResponse`; the frontend
  consumes it with `EventSource` (≈ a one-way WebSocket). Each agent → one event with its
  structured findings; final event → the prediction.
- Because the analysis agents run in one parallel superstep, they arrive in **real
  completion order** (light-data agents like weather/track first; OpenF1-heavy agents like
  grid/practice later) — honest progress, not a fixed cadence.
- **Fallback (cheaper) option:** keep the blocking call but include `agents_output` in the
  response and reveal each card client-side. Loses the live "pop-in" but needs no
  streaming plumbing.
- Replace the stale `"Prediction agents coming in Phase 3"` error placeholder in
  `PredictSheet.tsx` (Phase 3 is done).

### What to show per agent
| Agent | Key content |
|---|---|
| Grid & Sprint | Pole + front row, top-6 grid with quali gaps, sprint podium, analyst notes (lead card) |
| Practice | Best-lap vs long-run pace ranks, surprise performers, underperformers |
| Weather | Temp, rain %, wet-race flag (prominent banner if wet) |
| Driver / Car | Per-driver form, per-team pace + reliability |
| Track | Overtaking difficulty, tyre degradation, safety-car probability |
| Strategy | Pit windows, compounds, undercut viability |

Higher-level visuals worth adding: a **grid → predicted-finish delta** (arrows for who
gains/loses places) and **win-probability bars** (we already compute `driver_probabilities`
but never render them).

---

## 3. Problem B — Two kinds of agent hallucination

The architecture (parallel specialists → one Sonnet synthesiser) is sound and stays. But
two distinct defects produce untrustworthy agent output, each with a **different** fix.

### Type A — inventing data we already have (fix: data routing, NOT chaining)
- `driver_agent.py` makes the LLM fabricate `qualifying_pace`, `track_wins`,
  `avg_finish_position`, etc.
- `car_agent.py` estimates `reliability_score` and `recent_performance` from vibes.
- These fields are guessed even though we now fetch the **real** grid (Grid agent) and can
  compute reliability from retirement history.
- **Fix:** route real data into these agents (or let synthesis use the real signals and
  stop asking the weaker Haiku agents to invent numbers). Chaining LLM outputs would *not*
  help here — the missing input is a fact, not another agent's opinion.

### Type B — reasoning about the wrong world (fix: add a dependency edge)
- `strategy_agent.py` analyses **last year's dry stints** and outputs pit windows +
  compounds with **no knowledge of the forecast**. On a wet race it confidently produces
  dry-race strategy (wrong tyres, wrong stop count, ignores extra safety cars), and that
  misleading output is fed to synthesis as if it were fact.
- **Fix:** give Strategy the upstream facts it genuinely needs. Add LangGraph edges so
  Strategy runs *after* the agents whose output changes its answer:
  - **Weather → Strategy** (strong: wet changes tyres, stops, safety-car odds).
  - **Track → Strategy** (moderate: pit windows depend on tyre degradation + safety-car
    probability, which the Track agent produces).

> Note: there is no separate "tyre" agent. Tyre degradation is estimated inside the
> **Track** agent; long-run pace is computed in **Practice**. The real dependency chain is
> **weather + track(degradation, safety-car) → strategy**.

### Design rule (to avoid over-chaining)
Add a dependency edge **only where the downstream agent literally cannot be correct
without the upstream fact.** `weather → strategy` passes this test; `weather → track` does
not (a circuit's layout doesn't change with the forecast). Every edge trades latency and
error-propagation for conditioning, so keep them minimal. The heavy cross-domain combining
stays in the synthesis agent, which sees all signals at once.

---

## 4. Problem C — Accuracy is unmeasured

We assert "90–95%" as a goal but have no measurement. Every change in §3 is a hypothesis
until proven.

### Proposed solution
- **Back-testing:** run the full pipeline over already-completed 2026 races (results are
  available via Ergast) and record predicted-vs-actual podium hit-rate and winner accuracy.
  This lets us tune signal weights and *prove* each accuracy change helps rather than
  assuming. Highest-leverage item on this list.
- Track a simple calibration metric (e.g. podium hit-rate, Brier score on
  `driver_probabilities`) over time.

### Honest expectation
Exact-*winner* accuracy in F1 tops out around 45–55% even for strong grid-based models —
90–95% on the winner is not physically achievable. The realistic, meaningful target is
**podium hit-rate** (~70–85% of getting 2–3 of the 3 right), which `/api/predictions/stats`
already measures after each race.

---

## 5. Additional accuracy signals (backlog, prioritised)

Available in the free APIs but not yet used (see the services inventory):
1. **Richer race-time weather** — wind, track temp, and especially **rain timing**
   (OpenWeather hourly). Rain is the biggest upset driver; a wet forecast should *discount*
   the grid signal. We currently keep only temp/conditions/probability.
2. **Per-circuit pole→win conversion prior** — Ergast has decades of grid-vs-finish. Pole
   is far less decisive at Silverstone (good overtaking) than at Monaco. Telling the model
   *how much* to trust the grid per circuit is the smartest single addition.
3. **Tyre-degradation slope** from practice long runs (we compute the median, not the
   trend; Silverstone is high-deg).
4. **Form momentum** — last 3–5 races trend (rising/falling), not just standings position.

---

## 6. Proposed sequencing

1. **Agent transparency** (§2) — SSE streaming + real agent cards. Most visible win; makes
   everything else demoable.
2. **Hallucination fixes** (§3) — weather→strategy + track→strategy edges, and data routing
   into driver/car. Surgical, no rewrite.
3. **Back-testing** (§4) — so steps 1–2 and all future accuracy work are *measured*.
4. **Signal backlog** (§5) — weather timing + pole-conversion prior first.

---

## 7. Files likely touched (for reference, not a commitment)

- `backend/routes/predictions.py` — streaming endpoint / include `agents_output`.
- `backend/agents/orchestrator.py` — add `weather → strategy`, `track → strategy` edges.
- `backend/agents/strategy_agent.py` — consume weather + track output.
- `backend/agents/driver_agent.py`, `car_agent.py` — stop fabricating; use real data.
- `frontend/src/components/PredictSheet.tsx` — real per-agent cards, SSE consumption,
  probability bars, grid→finish delta; remove stale Phase-3 placeholder.
- `frontend/src/lib/api.ts` — streaming fetcher.
- New: a back-test script/route over completed 2026 races.
