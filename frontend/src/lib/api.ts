// The browser talks to the backend on a host-reachable URL (localhost:8000);
// server components inside Docker must use the docker-internal hostname
// (BACKEND_URL = http://backend:8000) since localhost there is the frontend
// container itself. `typeof window` picks the right one per bundle.
export const API_URL =
  (typeof window === "undefined" ? process.env.BACKEND_URL : undefined) ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

// ─── Health ──────────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: "ok" | "degraded";
  mongo: "ok" | "down";
  redis: "ok" | "down";
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

// ─── Races ───────────────────────────────────────────────────────────────────

export interface Race {
  name: string;
  circuit: string;
  circuit_id: string;
  location: string;
  country: string;
  lat: string | null;
  lon: string | null;
  date: string;
  round: number;
  year: number;
}

export async function fetchRaces(year: number): Promise<Race[]> {
  const res = await fetch(`${API_URL}/api/races?year=${year}`, {
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error(`Failed to fetch races: ${res.status}`);
  return res.json();
}

// ─── Circuit history ──────────────────────────────────────────────────────────

export interface CircuitWinner {
  year: number;
  race: string;
  winner: string;
  winner_id: string;
  constructor: string;
}

export async function fetchCircuitHistory(
  circuitId: string
): Promise<CircuitWinner[]> {
  const res = await fetch(`${API_URL}/api/races/${circuitId}/history`, {
    next: { revalidate: 86400 },
  });
  if (!res.ok)
    throw new Error(`Failed to fetch circuit history: ${res.status}`);
  return res.json();
}

// ─── Driver stats ─────────────────────────────────────────────────────────────

export interface DriverCircuitResult {
  year: number;
  grid: number;
  position: number;
  points: number;
  status: string | null;
}

export interface DriverStats {
  driver_id: string;
  circuit: string;
  starts: number;
  wins: number;
  podiums: number;
  avg_finish: number | null;
  best_finish: number | null;
  results: DriverCircuitResult[];
}

export async function fetchDriverStats(
  driverId: string,
  circuit: string
): Promise<DriverStats> {
  const res = await fetch(
    `${API_URL}/api/drivers/${driverId}/stats/${circuit}`,
    { next: { revalidate: 86400 } }
  );
  if (!res.ok) throw new Error(`Failed to fetch driver stats: ${res.status}`);
  return res.json();
}

// ─── Predictions ─────────────────────────────────────────────────────────────

export interface DriverProbability {
  driver: string;
  probability: number;
}

export interface PredictionResult {
  winner: string;
  podium: [string, string, string];
  confidence: number;
  reasoning: string;
  alternative_scenario: string;
  driver_probabilities: DriverProbability[];
}

export async function triggerPrediction(
  race: string,
  year: number
): Promise<PredictionResult> {
  const res = await fetch(`${API_URL}/api/predictions/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ race, year }),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Prediction failed: ${res.status}`);
  }
  return res.json();
}

// ─── Streamed prediction (per-agent results via Server-Sent Events) ──────────
// The backend emits one event per analysis agent as it completes, then a final
// event carrying the podium. Shapes mirror the backend Pydantic models.

export interface GridDriverOut {
  driver: string;
  grid_position: number;
  quali_best_time: number | null;
}

export interface SprintResultOut {
  driver: string;
  sprint_finish_position: number;
  sprint_points: number | null;
}

export interface GridOutput {
  data_available: boolean;
  session_analyzed: string;
  is_sprint_weekend: boolean;
  pole_sitter: string | null;
  front_row: string[];
  grid_order: GridDriverOut[];
  sprint_results: SprintResultOut[] | null;
  notes: string;
}

export interface PracticeDriverPaceOut {
  name: string;
  best_lap_rank: number;
  long_run_pace_rank: number;
  notes: string;
}

export interface PracticeOutput {
  data_available: boolean;
  session_analyzed: string;
  fastest_drivers: PracticeDriverPaceOut[];
  surprise_performers: string[];
  underperformers: string[];
  summary: string;
}

export interface WeatherOutput {
  temperature: number;
  conditions: string;
  rain_probability: number;
  wet_race_likely: boolean;
}

export interface DriverStatOut {
  name: string;
  track_wins: number;
  track_podiums: number;
  avg_finish_position: number;
  current_form: number;
  qualifying_pace: number;
}

export interface DriverOutput {
  drivers: DriverStatOut[];
}

export interface TeamStatOut {
  name: string;
  car_type: string;
  recent_performance: number;
  reliability_score: number;
}

export interface CarOutput {
  teams: TeamStatOut[];
}

export interface TrackOutput {
  circuit_type: string;
  overtaking_difficulty: string;
  tire_degradation: string;
  safety_car_probability: number;
  key_characteristics: string[];
}

export interface StrategyOutput {
  optimal_pit_windows: number[];
  tire_compounds: string[];
  undercut_opportunity: boolean;
  safety_car_impact: string;
}

// One SSE frame. For analysis agents `output` holds that agent's analysis; the
// terminal frame has agent === "prediction" with either `prediction` or `detail`.
export interface AgentStreamEvent {
  agent: string;
  status: "done" | "error";
  output?: unknown;
  prediction?: PredictionResult;
  detail?: string;
}

export interface StreamHandlers {
  onAgent: (agent: string, output: unknown) => void;
  onDone: (prediction: PredictionResult) => void;
  onError: (message: string) => void;
}

/**
 * Subscribe to a streamed prediction. Returns an unsubscribe function that
 * closes the connection (call it on unmount / sheet close).
 */
// The backend caps the pipeline at 150s; this is the client-side backstop so a
// stalled stream can't leave the UI spinning forever.
const STREAM_WATCHDOG_MS = 180_000;

export function streamPrediction(
  race: string,
  year: number,
  handlers: StreamHandlers
): () => void {
  const url = `${API_URL}/api/predictions/predict/stream?race=${encodeURIComponent(
    race
  )}&year=${year}`;
  const es = new EventSource(url);
  let finished = false;

  const finish = () => {
    finished = true;
    clearTimeout(watchdog);
    es.close();
  };

  const watchdog = setTimeout(() => {
    if (finished) return;
    finish();
    handlers.onError("The prediction stream timed out");
  }, STREAM_WATCHDOG_MS);

  es.onmessage = (e) => {
    let data: AgentStreamEvent;
    try {
      data = JSON.parse(e.data);
    } catch (err) {
      console.error("Dropped malformed prediction-stream frame:", err, e.data);
      return;
    }
    if (data.agent === "prediction") {
      finish();
      if (data.status === "error" || !data.prediction) {
        handlers.onError(data.detail ?? "Prediction failed");
      } else {
        handlers.onDone(data.prediction);
      }
    } else {
      handlers.onAgent(data.agent, data.output);
    }
  };

  es.onerror = () => {
    if (finished) return; // normal close after the terminal event
    finish();
    handlers.onError("Lost connection to the prediction stream");
  };

  return finish;
}

// ─── Actual race result (for backtesting past predictions) ───────────────────

export interface RaceResult {
  race: string;
  winner: string;
  podium: string[];
  constructor: string;
}

export async function fetchRaceResult(
  year: number,
  round: number
): Promise<RaceResult | null> {
  const res = await fetch(
    `${API_URL}/api/races/result?year=${year}&round=${round}`,
    { next: { revalidate: 86400 } }
  );
  if (!res.ok) throw new Error(`Failed to fetch race result: ${res.status}`);
  return res.json();
}

// ─── Prediction history (predicted vs actual) ────────────────────────────────

export interface PredictionHistoryItem {
  _id: string;
  race: string;
  year: number;
  predicted_winner: string;
  predicted_podium: string[];
  confidence: number;
  actual_winner: string | null;
  actual_podium: string[] | null;
  was_correct: boolean | null;
  podium_correct_count: number | null;
  created_at: string;
}

export async function fetchPredictionHistory(): Promise<PredictionHistoryItem[]> {
  const res = await fetch(`${API_URL}/api/predictions/history`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch prediction history: ${res.status}`);
  return res.json();
}

// ─── Prediction stats (dashboard scorecard) ─────────────────────────────────

export interface CircuitAccuracy {
  circuit_id: string;
  winner_correct: number;
  graded: number;
}

export interface PredictionStats {
  total: number;
  graded: number;
  winner_correct: number;
  winner_accuracy: number; // 0–1
  avg_podium_hits: number; // 0–3
  by_circuit: CircuitAccuracy[];
}

export async function fetchPredictionStats(): Promise<PredictionStats> {
  const res = await fetch(`${API_URL}/api/predictions/stats`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch prediction stats: ${res.status}`);
  return res.json();
}

// ─── Live Race Center ────────────────────────────────────────────────────────

export interface LiveSession {
  mode: "live" | "replay" | "none";
  session_key: number;
  meeting_name: string | null;
  session_name: string | null;
  circuit_short_name: string | null;
  country_name: string | null;
  date_start: string | null;
  date_end: string | null;
  year: number | null;
}

export interface TrackPoint {
  x: number;
  y: number;
}

export interface TrackOutline {
  session_key: number;
  points: TrackPoint[];
}

export interface LiveCar {
  num: number;
  code: string;
  colour: string;
  x: number;
  y: number;
}

export interface LiveMap {
  at: string;
  cars: LiveCar[];
}

export async function fetchLiveSession(sessionKey?: number): Promise<LiveSession> {
  const q = sessionKey ? `?session_key=${sessionKey}` : "";
  const res = await fetch(`${API_URL}/api/live/session${q}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to resolve live session: ${res.status}`);
  return res.json();
}

export async function fetchTrackOutline(
  sessionKey: number
): Promise<TrackOutline> {
  const res = await fetch(`${API_URL}/api/live/track?session_key=${sessionKey}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch track outline: ${res.status}`);
  return res.json();
}

export async function fetchLiveMap(
  sessionKey: number,
  at: string,
  signal?: AbortSignal
): Promise<LiveMap> {
  const res = await fetch(
    `${API_URL}/api/live/map?session_key=${sessionKey}&at=${encodeURIComponent(at)}`,
    { cache: "no-store", signal }
  );
  if (!res.ok) throw new Error(`Failed to fetch live map: ${res.status}`);
  return res.json();
}

// ─── Standings (proxied through the backend's Redis-cached Ergast service) ───

export interface DriverStanding {
  position: number;
  points: number;
  wins: number;
  driver_id: string;
  driver_name: string;
  team: string;
}

export interface ConstructorStanding {
  position: number;
  points: number;
  wins: number;
  constructor_id: string;
  constructor_name: string;
}

interface BackendDriverStanding {
  position: number;
  points: number;
  wins: number;
  driver: string;
  driver_id: string;
  team: string;
}

interface BackendConstructorStanding {
  position: number;
  points: number;
  wins: number;
  constructor: string;
  constructor_id: string;
}

export async function fetchDriverStandings(
  year: number
): Promise<DriverStanding[]> {
  const res = await fetch(`${API_URL}/api/standings/drivers?year=${year}`, {
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error(`Failed to fetch standings: ${res.status}`);
  const data: BackendDriverStanding[] = await res.json();
  return data.map(({ driver, ...rest }) => ({ ...rest, driver_name: driver }));
}

export async function fetchConstructorStandings(
  year: number
): Promise<ConstructorStanding[]> {
  const res = await fetch(`${API_URL}/api/standings/constructors?year=${year}`, {
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error(`Failed to fetch constructor standings: ${res.status}`);
  const data: BackendConstructorStanding[] = await res.json();
  return data.map(({ constructor, ...rest }) => ({
    ...rest,
    constructor_name: constructor,
  }));
}
