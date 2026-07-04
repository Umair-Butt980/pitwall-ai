# Feature: Live Grid + Sprint signal (Grid & Sprint agent)

> Approved implementation plan, kept for reference. Shipped ahead of the 2026 British GP.

## Context

PitWall AI predicts F1 podiums via 6 LangGraph analysis agents (weather, driver, car,
track, strategy, practice) → a Sonnet synthesis agent. Recent work grounded agents in
live championship standings and added a practice-pace agent to stop the pipeline from
predicting the same three drivers every race.

**The problem:** The 2026 British GP (Sun Jul 5) is a **Sprint weekend**, which breaks
our best signals and exposes our biggest gaps:

- Only **one** free practice runs on a sprint weekend (FP1, Fri). The practice agent
  looks for FP2/FP3 first — they don't exist — so its pace signal is thin this weekend.
- The two strongest predictors that *do* exist right now were fetched **nowhere**:
  - **GP Qualifying → the starting grid** (Sat 16:00 BST). Grid position is the single
    biggest predictor of a race result.
  - **The Sprint race result** (Sat 12:00 BST) — a real race at Silverstone in current
    conditions, the freshest race-pace signal possible.

Both are available from OpenF1 minutes after each session (`session_result`,
`starting_grid`). The prediction is intended to be run **after GP qualifying**, so the
real Sunday grid is available.

**Goal:** Add one new **Grid & Sprint agent** that pulls the live grid + sprint results
and weight it as the strongest signal in synthesis. Optimize for **podium hit-rate**
(realistically ~70–85%; exact-winner in F1 tops out ~45–55%, so 90–95% exact winner is
not physically achievable — we set that expectation honestly and maximize signal).

Scope: **focused high-ROI only** (no Q1/Q2/Q3 micro-detail, weather enrichment, or model
swap in this pass).

## Approach

Mirror the existing `practice_agent.py` pattern exactly — same structure, Haiku model,
graceful `data_available=False` degradation, real numeric work done in Python (grid
positions are facts, not LLM estimates; the LLM only summarizes and flags anomalies).

### 1. OpenF1 service — new fetchers
`backend/services/openf1_service.py`:
- `get_session_result(session_key)` → `GET /session_result?session_key=...` (works for
  qualifying and sprint; qualifying rows carry Q1/Q2/Q3 arrays, race rows carry position).
- `get_starting_grid(session_key)` → `GET /starting_grid?session_key=...` (keyed off the
  Race session; reflects qualifying + penalties).
- Cache TTL short (300s) — these go live during the weekend.
- Session resolution reuses the `get_sessions(year, session_name)` + circuit/race-name
  matching heuristic from `practice_agent.py` / `strategy_agent.py`. Fetch `"Qualifying"`,
  `"Race"`, and `"Sprint"`.

### 2. Response models
`backend/models/prediction.py`:
- `GridDriver{ driver, grid_position, quali_best_time|None }`
- `SprintResult{ driver, sprint_finish_position, sprint_points|None }`
- `GridAnalysis{ data_available, session_analyzed, is_sprint_weekend, pole_sitter|None,
  front_row: list[str], grid_order: list[GridDriver], sprint_results: list[SprintResult]|None,
  notes }`

### 3. New agent
`backend/agents/grid_agent.py` (Haiku, copies the shape of `practice_agent.py`):
- Resolve the weekend's Qualifying + Race sessions by name/circuit match.
- Build `grid_order` + `pole_sitter` + `front_row` from `get_starting_grid`, falling back
  to qualifying `session_result` ordering if the grid endpoint is empty pre-race.
- If a `"Sprint"` session exists, pull `get_session_result` → sprint finishing order
  (`sprint_results`, `is_sprint_weekend=True`).
- LLM job: produce `notes` — grid penalties, a front-row starter low in the championship
  (a dark-horse from the front), or a sprint result contradicting the standings. All
  positions passed as computed facts.
- `_empty(reason)` → `GridAnalysis(data_available=False, session_analyzed="none", ...)`
  when qualifying hasn't run yet (mid-weekend / future-race predictions still work).

### 4. Wiring (mirrors how `practice` was wired)
- `backend/agents/state.py` — add `grid_output` key to `PredictionState`.
- `backend/agents/orchestrator.py` — register `grid` node, add to `_ANALYSIS_NODES`,
  `START → grid → prediction` fan-out/fan-in.
- `backend/routes/predictions.py` — add `grid_output: None` to `initial_state`; include it
  in the `_save_prediction` `agents_output` blob.
- `backend/agents/prediction_agent.py` — add a Grid & Sprint section via `_format_section`,
  framed as the strongest signal (the STARTING GRID outweighs standings and practice for
  the front runners; SPRINT results are corroborating race-pace evidence). Anchor the
  podium on the front of the grid; only move a front-row starter down for a concrete
  reason (grid penalty, wet weather, poor race pace).

### 5. Frontend
`frontend/src/components/PredictSheet.tsx` — add an 8th `AgentStatusRow` "Grid & Sprint"
(pattern identical to the "Practice Pace" row).

## Files changed
- `backend/services/openf1_service.py` (2 new methods)
- `backend/models/prediction.py` (3 new models)
- `backend/agents/grid_agent.py` (new)
- `backend/agents/state.py`, `backend/agents/orchestrator.py`,
  `backend/routes/predictions.py`, `backend/agents/prediction_agent.py` (wiring)
- `frontend/src/components/PredictSheet.tsx` (1 new row)

## Out of scope (future)
- Q1/Q2/Q3 split detail, richer weather (wind/humidity), replacing other LLM-estimated
  fields with computed values.
- Synthesis model id: `prediction_agent.py` uses `claude-sonnet-4-6` — verify it still
  resolves (current tier is `claude-sonnet-5`); not changed in this pass.

## Verification (after GP qualifying runs)
1. `docker compose build backend && docker compose up -d`.
2. Sanity-check the OpenF1 fetchers resolve the British GP sessions via
   `docker compose exec backend python -c "..."` (get_sessions 2026 Qualifying/Race/Sprint
   → confirm a Silverstone session_key, then get_starting_grid returns rows).
3. `curl -XPOST localhost:8000/api/predictions/predict -d '{"race":"British Grand Prix","year":2026}'`
   → confirm `agents_output.grid.data_available == true`, `grid_order` matches the actual
   Saturday qualifying result, and the podium reflects the front rows / sprint finishers.
4. Frontend predict sheet for the British GP → the "Grid & Sprint" row runs and the podium
   reveal reflects the grid.
5. After Sunday's race, `GET /api/predictions/stats` → the prediction auto-grades so we can
   measure podium hit-rate against the real result.
