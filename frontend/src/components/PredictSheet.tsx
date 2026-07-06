"use client";

import { useEffect, useReducer } from "react";
import { Cloud, User, Car, Map, GitBranch, Timer, Flag, Brain } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import AgentStatusRow, { type AgentStatus } from "@/components/AgentStatusRow";
import {
  streamPrediction,
  fetchRaceResult,
  type PredictionResult,
  type RaceResult,
  type GridOutput,
  type PracticeOutput,
  type WeatherOutput,
  type DriverOutput,
  type CarOutput,
  type TrackOutput,
  type StrategyOutput,
} from "@/lib/api";

const AGENTS = [
  { key: "grid", name: "Grid & Sprint", description: "Qualifying grid & sprint result", Icon: Flag },
  { key: "practice", name: "Practice Pace", description: "FP1–FP3 lap analysis", Icon: Timer },
  { key: "weather", name: "Weather Agent", description: "Analysing race-day forecast", Icon: Cloud },
  { key: "driver", name: "Driver Performance", description: "Track record & current form", Icon: User },
  { key: "car", name: "Car Performance", description: "Team & car analysis", Icon: Car },
  { key: "track", name: "Track Analysis", description: "Circuit characteristics", Icon: Map },
  { key: "strategy", name: "Strategy Agent", description: "Tyre & pit stop modelling", Icon: GitBranch },
  { key: "prediction", name: "Prediction Synthesis", description: "Claude finalises the podium", Icon: Brain },
] as const;

type AgentKey = (typeof AGENTS)[number]["key"];
type AgentStatuses = Record<AgentKey, AgentStatus>;

const ANALYSIS_KEYS = AGENTS.filter((a) => a.key !== "prediction").map(
  (a) => a.key
) as Exclude<AgentKey, "prediction">[];

// ─── Reducer ─────────────────────────────────────────────────────────────────
// Batching all sheet state into one reducer avoids multiple setState calls
// inside useEffect (which triggers the react-hooks/set-state-in-effect lint rule).

interface SheetState {
  statuses: AgentStatuses;
  outputs: Partial<Record<AgentKey, unknown>>;
  phase: "idle" | "running" | "done" | "error";
  result: PredictionResult | null;
  actual: RaceResult | null; // real podium, fetched for past races
  errorMsg: string;
  reasoningOpen: boolean;
}

type SheetAction =
  | { type: "RESET" }
  | { type: "START" }
  | { type: "AGENT_DONE"; key: AgentKey; output: unknown }
  | { type: "SUCCESS"; result: PredictionResult }
  | { type: "SET_ACTUAL"; actual: RaceResult | null }
  | { type: "ERROR"; message: string }
  | { type: "TOGGLE_REASONING" };

const INITIAL_STATUSES: AgentStatuses = {
  grid: "pending",
  practice: "pending",
  weather: "pending",
  driver: "pending",
  car: "pending",
  track: "pending",
  strategy: "pending",
  prediction: "pending",
};

// At kick-off every analysis agent runs in parallel; synthesis waits its turn.
const RUNNING_STATUSES: AgentStatuses = {
  ...INITIAL_STATUSES,
  ...(Object.fromEntries(ANALYSIS_KEYS.map((k) => [k, "running"])) as Record<
    Exclude<AgentKey, "prediction">,
    AgentStatus
  >),
};

const INITIAL_STATE: SheetState = {
  statuses: INITIAL_STATUSES,
  outputs: {},
  phase: "idle",
  result: null,
  actual: null,
  errorMsg: "",
  reasoningOpen: false,
};

function reducer(state: SheetState, action: SheetAction): SheetState {
  switch (action.type) {
    case "RESET":
      return INITIAL_STATE;
    case "START":
      return { ...INITIAL_STATE, phase: "running", statuses: RUNNING_STATUSES };
    case "AGENT_DONE": {
      const statuses = { ...state.statuses, [action.key]: "done" as AgentStatus };
      // Once every analysis agent is in, the synthesis step is what's running.
      const allAnalysisDone = ANALYSIS_KEYS.every((k) => statuses[k] === "done");
      if (allAnalysisDone && statuses.prediction === "pending") {
        statuses.prediction = "running";
      }
      return {
        ...state,
        statuses,
        outputs: { ...state.outputs, [action.key]: action.output },
      };
    }
    case "SUCCESS":
      return {
        ...state,
        statuses: { ...state.statuses, prediction: "done" },
        phase: "done",
        result: action.result,
      };
    case "SET_ACTUAL":
      return { ...state, actual: action.actual };
    case "ERROR":
      return { ...state, phase: "error", errorMsg: action.message };
    case "TOGGLE_REASONING":
      return { ...state, reasoningOpen: !state.reasoningOpen };
    default:
      return state;
  }
}

// ─── Component ───────────────────────────────────────────────────────────────

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  race: string;
  year: number;
  round?: number;
  isPast?: boolean; // when true, fetch the real result and compare (backtest)
}

const PODIUM_STYLES: Record<number, { label: string; color: string }> = {
  0: { label: "P1", color: "text-yellow-400 border-yellow-400/40 bg-yellow-400/10" },
  1: { label: "P2", color: "text-zinc-300 border-zinc-400/40 bg-zinc-400/10" },
  2: { label: "P3", color: "text-amber-600 border-amber-600/40 bg-amber-600/10" },
};

export default function PredictSheet({
  open,
  onOpenChange,
  race,
  year,
  round,
  isPast,
}: Props) {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const { statuses, phase, result, actual, errorMsg, reasoningOpen } = state;
  const outputs = state.outputs ?? {}; // guard against stale HMR state shape

  useEffect(() => {
    if (!open) {
      dispatch({ type: "RESET" });
      return;
    }

    dispatch({ type: "START" });

    let cancelled = false;
    const unsubscribe = streamPrediction(race, year, {
      onAgent: (agent, output) => {
        if (cancelled) return;
        if (agent in INITIAL_STATUSES) {
          dispatch({ type: "AGENT_DONE", key: agent as AgentKey, output });
        }
      },
      onDone: (prediction) => {
        if (cancelled) return;
        dispatch({ type: "SUCCESS", result: prediction });
        // For a past race, pull the real result so we can show predicted vs actual.
        if (isPast && round) {
          fetchRaceResult(year, round)
            .then((res) => {
              if (!cancelled) dispatch({ type: "SET_ACTUAL", actual: res });
            })
            .catch(() => {
              /* best-effort — comparison just won't render */
            });
        }
      },
      onError: (message) => {
        if (!cancelled) dispatch({ type: "ERROR", message });
      },
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [open, race, year, round, isPast]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col gap-0 overflow-y-auto sm:max-w-lg">
        <SheetHeader className="px-6 pt-6 pb-4 border-b border-border/50">
          <SheetTitle className="flex items-center gap-2">
            <span className="text-primary font-mono">🏎️</span>
            Race Prediction
          </SheetTitle>
          <SheetDescription>
            {race} · {year} Season
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-3 p-6">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Multi-Agent Analysis
          </p>

          {AGENTS.map(({ key, name, description, Icon }) => (
            <AgentStatusRow
              key={key}
              name={name}
              description={description}
              Icon={Icon}
              status={statuses[key]}
            >
              {renderAgentDetails(key, outputs[key])}
            </AgentStatusRow>
          ))}

          {phase === "done" && result && (
            <div className="mt-4 flex flex-col gap-4">
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                Predicted Podium
              </p>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <PodiumCard position={1} driver={result.podium[1]} />
                <PodiumCard position={0} driver={result.podium[0]} elevated />
                <PodiumCard position={2} driver={result.podium[2]} />
              </div>

              <p className="text-center text-sm text-muted-foreground">
                Overall confidence:{" "}
                <span className="font-semibold text-foreground">
                  {Math.round(result.confidence * 100)}%
                </span>
              </p>

              {result.driver_probabilities?.length > 0 && (
                <WinProbabilities probabilities={result.driver_probabilities} />
              )}

              {isPast && actual && (
                <ActualResultComparison result={result} actual={actual} />
              )}

              <div className="rounded-lg border border-border/50 bg-card/50">
                <button
                  onClick={() => dispatch({ type: "TOGGLE_REASONING" })}
                  aria-expanded={reasoningOpen}
                  className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium"
                >
                  <span>AI Reasoning</span>
                  <span className="text-muted-foreground">
                    {reasoningOpen ? "▲" : "▼"}
                  </span>
                </button>
                {reasoningOpen && (
                  <p className="px-4 pb-4 text-sm text-muted-foreground leading-relaxed">
                    {result.reasoning}
                  </p>
                )}
              </div>

              {result.alternative_scenario && (
                <div className="rounded-lg border border-border/50 bg-muted/20 px-4 py-3">
                  <p className="mb-1 text-xs font-medium text-muted-foreground uppercase tracking-widest">
                    Alternative Scenario
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {result.alternative_scenario}
                  </p>
                </div>
              )}
            </div>
          )}

          {phase === "error" && (
            <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-5 text-center">
              <p className="text-2xl mb-2">⚠️</p>
              <p className="font-medium text-sm">Prediction failed</p>
              <p className="text-xs text-muted-foreground mt-1">
                The agent pipeline hit an error. Please try again in a moment.
              </p>
              {errorMsg && (
                <p className="mt-2 font-mono text-xs text-destructive">{errorMsg}</p>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ─── Per-agent detail renderers ──────────────────────────────────────────────

function renderAgentDetails(key: AgentKey, output: unknown): React.ReactNode {
  if (output == null || key === "prediction") return null;
  switch (key) {
    case "grid":
      return <GridDetails g={output as GridOutput} />;
    case "practice":
      return <PracticeDetails p={output as PracticeOutput} />;
    case "weather":
      return <WeatherDetails w={output as WeatherOutput} />;
    case "driver":
      return <DriverDetails d={output as DriverOutput} />;
    case "car":
      return <CarDetails c={output as CarOutput} />;
    case "track":
      return <TrackDetails t={output as TrackOutput} />;
    case "strategy":
      return <StrategyDetails s={output as StrategyOutput} />;
    default:
      return null;
  }
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground">
      {children}
    </span>
  );
}

function KV({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
      <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
    </div>
  );
}

function GridDetails({ g }: { g: GridOutput }) {
  if (!g?.data_available) {
    return (
      <p className="text-xs text-muted-foreground">
        {g?.notes || "Qualifying hasn't run for this event yet."}
      </p>
    );
  }
  const poleTime = g.grid_order?.[0]?.quali_best_time ?? null;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {g.pole_sitter && <Chip>Pole: {g.pole_sitter}</Chip>}
        {g.is_sprint_weekend && <Chip>Sprint weekend</Chip>}
      </div>

      <ol className="flex flex-col gap-1">
        {g.grid_order.slice(0, 6).map((row) => {
          const gap =
            poleTime != null && row.quali_best_time != null
              ? row.quali_best_time - poleTime
              : null;
          return (
            <li
              key={row.grid_position}
              className="flex items-center justify-between text-xs"
            >
              <span>
                <span className="mr-2 font-mono text-muted-foreground">
                  P{row.grid_position}
                </span>
                {row.driver}
              </span>
              {gap != null && (
                <span className="font-mono text-muted-foreground">
                  {gap === 0 ? "pole" : `+${gap.toFixed(3)}`}
                </span>
              )}
            </li>
          );
        })}
      </ol>

      {g.sprint_results && g.sprint_results.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-foreground">Sprint result</p>
          <ol className="flex flex-col gap-0.5">
            {g.sprint_results.slice(0, 3).map((s) => (
              <li
                key={s.sprint_finish_position}
                className="text-xs text-muted-foreground"
              >
                <span className="mr-2 font-mono">P{s.sprint_finish_position}</span>
                {s.driver}
              </li>
            ))}
          </ol>
        </div>
      )}

      {g.notes && (
        <p className="text-xs leading-relaxed text-muted-foreground">{g.notes}</p>
      )}
    </div>
  );
}

function PracticeDetails({ p }: { p: PracticeOutput }) {
  if (!p?.data_available) {
    return (
      <p className="text-xs text-muted-foreground">
        {p?.summary || "No practice data available for this event yet."}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <Chip>Session: {p.session_analyzed}</Chip>
      <ol className="flex flex-col gap-1">
        {p.fastest_drivers.slice(0, 6).map((d) => (
          <li key={d.name} className="flex items-center justify-between text-xs">
            <span>{d.name}</span>
            <span className="font-mono text-muted-foreground">
              lap #{d.best_lap_rank} · run #{d.long_run_pace_rank}
            </span>
          </li>
        ))}
      </ol>
      {p.surprise_performers?.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-xs text-muted-foreground">Dark horses:</span>
          {p.surprise_performers.map((n) => (
            <Chip key={n}>{n}</Chip>
          ))}
        </div>
      )}
      {p.summary && (
        <p className="text-xs leading-relaxed text-muted-foreground">{p.summary}</p>
      )}
    </div>
  );
}

function WeatherDetails({ w }: { w: WeatherOutput }) {
  return (
    <div className="flex flex-col gap-1.5">
      <KV label="Temperature" value={`${Math.round(w.temperature)}°C`} />
      <KV label="Conditions" value={w.conditions} />
      <KV label="Rain probability" value={`${Math.round(w.rain_probability * 100)}%`} />
      {w.wet_race_likely && (
        <p className="mt-1 rounded-md bg-blue-500/10 px-2 py-1 text-xs text-blue-400">
          Wet race likely — grid order matters less.
        </p>
      )}
    </div>
  );
}

function DriverDetails({ d }: { d: DriverOutput }) {
  const top = [...(d.drivers ?? [])]
    .sort((a, b) => b.current_form - a.current_form)
    .slice(0, 5);
  return (
    <ol className="flex flex-col gap-1.5">
      {top.map((driver) => (
        <li key={driver.name} className="flex items-center justify-between gap-2 text-xs">
          <span className="truncate">{driver.name}</span>
          <ScoreBar value={driver.current_form} />
        </li>
      ))}
    </ol>
  );
}

function CarDetails({ c }: { c: CarOutput }) {
  const top = [...(c.teams ?? [])]
    .sort((a, b) => b.recent_performance - a.recent_performance)
    .slice(0, 5);
  return (
    <ol className="flex flex-col gap-1.5">
      {top.map((team) => (
        <li key={team.name} className="flex items-center justify-between gap-2 text-xs">
          <span className="truncate">{team.name}</span>
          <ScoreBar value={team.recent_performance} />
        </li>
      ))}
    </ol>
  );
}

function TrackDetails({ t }: { t: TrackOutput }) {
  return (
    <div className="flex flex-col gap-1.5">
      <KV label="Circuit type" value={t.circuit_type} />
      <KV label="Overtaking" value={t.overtaking_difficulty} />
      <KV label="Tyre degradation" value={t.tire_degradation} />
      <KV
        label="Safety-car chance"
        value={`${Math.round(t.safety_car_probability * 100)}%`}
      />
      {t.key_characteristics?.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {t.key_characteristics.map((k) => (
            <Chip key={k}>{k}</Chip>
          ))}
        </div>
      )}
    </div>
  );
}

function StrategyDetails({ s }: { s: StrategyOutput }) {
  return (
    <div className="flex flex-col gap-2">
      {s.optimal_pit_windows?.length > 0 && (
        <KV label="Pit windows" value={`laps ${s.optimal_pit_windows.join(", ")}`} />
      )}
      <KV label="Undercut viable" value={s.undercut_opportunity ? "Yes" : "No"} />
      {s.tire_compounds?.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-xs text-muted-foreground">Compounds:</span>
          {s.tire_compounds.map((c) => (
            <Chip key={c}>{c}</Chip>
          ))}
        </div>
      )}
      {s.safety_car_impact && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          {s.safety_car_impact}
        </p>
      )}
    </div>
  );
}

function WinProbabilities({
  probabilities,
}: {
  probabilities: { driver: string; probability: number }[];
}) {
  const top = [...probabilities]
    .sort((a, b) => b.probability - a.probability)
    .slice(0, 8);
  const max = top[0]?.probability || 1;
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border/50 bg-card/50 p-4">
      <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
        Win Probability
      </p>
      {top.map((p) => (
        <div key={p.driver} className="flex items-center gap-2 text-xs">
          <span className="w-32 shrink-0 truncate">{p.driver}</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${(p.probability / max) * 100}%` }}
            />
          </div>
          <span className="w-10 shrink-0 text-right font-mono text-muted-foreground">
            {Math.round(p.probability * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}

function ActualResultComparison({
  result,
  actual,
}: {
  result: PredictionResult;
  actual: RaceResult;
}) {
  const winnerCorrect = result.podium[0] === actual.winner;
  const podiumHits = result.podium.filter((d) => actual.podium.includes(d)).length;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border/50 bg-muted/20 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
          Actual Result
        </p>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
            winnerCorrect
              ? "bg-primary/15 text-primary"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {winnerCorrect ? "✓ Winner correct" : "✗ Winner missed"}
        </span>
      </div>

      <ol className="flex flex-col gap-1.5">
        {actual.podium.map((driver, i) => {
          const predictedHere = result.podium[i] === driver;
          const predictedAtAll = result.podium.includes(driver);
          return (
            <li
              key={driver}
              className="flex items-center justify-between text-sm"
            >
              <span>
                <span className="mr-2 font-mono text-muted-foreground">
                  P{i + 1}
                </span>
                {driver}
              </span>
              <span className="text-xs">
                {predictedHere ? (
                  <span className="text-primary">✓ exact</span>
                ) : predictedAtAll ? (
                  <span className="text-yellow-400">~ on podium</span>
                ) : (
                  <span className="text-muted-foreground">missed</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-center text-xs text-muted-foreground">
        Podium accuracy:{" "}
        <span className="font-semibold text-foreground">{podiumHits}/3</span>
      </p>
    </div>
  );
}

function PodiumCard({
  position,
  driver,
  elevated,
}: {
  position: number;
  driver: string;
  elevated?: boolean;
}) {
  // Only P1–P3 exist; an out-of-range index (e.g. short podium from the API)
  // must render a placeholder rather than throw on destructuring undefined.
  const style = PODIUM_STYLES[position];
  if (!style || !driver) return null;
  const { label, color } = style;
  return (
    <div
      className={`flex flex-1 flex-col items-center gap-2 rounded-xl border px-4 py-4 text-center ${color} ${
        elevated ? "sm:py-6" : ""
      }`}
    >
      <span className={`text-2xl font-black ${color.split(" ")[0]}`}>{label}</span>
      <span className="font-semibold text-sm text-foreground">{driver}</span>
    </div>
  );
}
