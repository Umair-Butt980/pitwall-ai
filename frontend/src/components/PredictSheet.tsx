"use client";

import { useEffect, useReducer } from "react";
import { Cloud, User, Car, Map, GitBranch, Brain } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import AgentStatusRow, { type AgentStatus } from "@/components/AgentStatusRow";
import { triggerPrediction, type PredictionResult } from "@/lib/api";

const AGENTS = [
  { key: "weather", name: "Weather Agent", description: "Analysing race-day forecast", Icon: Cloud },
  { key: "driver", name: "Driver Performance", description: "Track record & current form", Icon: User },
  { key: "car", name: "Car Performance", description: "Team & car analysis", Icon: Car },
  { key: "track", name: "Track Analysis", description: "Circuit characteristics", Icon: Map },
  { key: "strategy", name: "Strategy Agent", description: "Tyre & pit stop modelling", Icon: GitBranch },
  { key: "prediction", name: "Prediction Synthesis", description: "Claude finalises the podium", Icon: Brain },
] as const;

type AgentKey = (typeof AGENTS)[number]["key"];
type AgentStatuses = Record<AgentKey, AgentStatus>;

// ─── Reducer ─────────────────────────────────────────────────────────────────
// Batching all sheet state into one reducer avoids multiple setState calls
// inside useEffect (which triggers the react-hooks/set-state-in-effect lint rule).

interface SheetState {
  statuses: AgentStatuses;
  phase: "idle" | "running" | "done" | "error";
  result: PredictionResult | null;
  errorMsg: string;
  reasoningOpen: boolean;
}

type SheetAction =
  | { type: "RESET" }
  | { type: "START" }
  | { type: "AGENT_RUNNING"; key: AgentKey }
  | { type: "SUCCESS"; result: PredictionResult }
  | { type: "ERROR"; message: string }
  | { type: "TOGGLE_REASONING" };

const INITIAL_STATUSES: AgentStatuses = {
  weather: "pending",
  driver: "pending",
  car: "pending",
  track: "pending",
  strategy: "pending",
  prediction: "pending",
};

const INITIAL_STATE: SheetState = {
  statuses: INITIAL_STATUSES,
  phase: "idle",
  result: null,
  errorMsg: "",
  reasoningOpen: false,
};

function reducer(state: SheetState, action: SheetAction): SheetState {
  switch (action.type) {
    case "RESET":
      return INITIAL_STATE;
    case "START":
      return { ...INITIAL_STATE, phase: "running" };
    case "AGENT_RUNNING":
      return {
        ...state,
        statuses: { ...state.statuses, [action.key]: "running" },
      };
    case "SUCCESS": {
      const done = Object.fromEntries(
        AGENTS.map((a) => [a.key, "done"])
      ) as AgentStatuses;
      return { ...state, statuses: done, phase: "done", result: action.result };
    }
    case "ERROR": {
      const done = Object.fromEntries(
        AGENTS.map((a) => [a.key, "done"])
      ) as AgentStatuses;
      return { ...state, statuses: done, phase: "error", errorMsg: action.message };
    }
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
}

const PODIUM_STYLES: Record<number, { label: string; color: string }> = {
  0: { label: "P1", color: "text-yellow-400 border-yellow-400/40 bg-yellow-400/10" },
  1: { label: "P2", color: "text-zinc-300 border-zinc-400/40 bg-zinc-400/10" },
  2: { label: "P3", color: "text-amber-600 border-amber-600/40 bg-amber-600/10" },
};

export default function PredictSheet({ open, onOpenChange, race, year }: Props) {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const { statuses, phase, result, errorMsg, reasoningOpen } = state;

  useEffect(() => {
    if (!open) {
      dispatch({ type: "RESET" });
      return;
    }

    dispatch({ type: "START" });

    // Stagger the agent "running" badges so the user sees progress even before
    // the API responds. Each agent lights up ~1.2s apart.
    const timers: ReturnType<typeof setTimeout>[] = [];
    AGENTS.forEach(({ key }, i) => {
      timers.push(
        setTimeout(
          () => dispatch({ type: "AGENT_RUNNING", key }),
          i * 1200
        )
      );
    });

    let cancelled = false;
    triggerPrediction(race, year)
      .then((data) => {
        if (!cancelled) dispatch({ type: "SUCCESS", result: data });
      })
      .catch((err: Error) => {
        if (!cancelled)
          dispatch({ type: "ERROR", message: err.message ?? "Unknown error" });
      });

    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
  }, [open, race, year]);

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
            />
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

              <div className="rounded-lg border border-border/50 bg-card/50">
                <button
                  onClick={() => dispatch({ type: "TOGGLE_REASONING" })}
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
            <div className="mt-4 rounded-lg border border-border/50 bg-muted/20 px-4 py-5 text-center">
              <p className="text-2xl mb-2">🔧</p>
              <p className="font-medium text-sm">Prediction agents coming in Phase 3</p>
              <p className="text-xs text-muted-foreground mt-1">
                The AI agent pipeline is being built. Check back once Phase 3 is
                complete.
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

function PodiumCard({
  position,
  driver,
  elevated,
}: {
  position: number;
  driver: string;
  elevated?: boolean;
}) {
  const { label, color } = PODIUM_STYLES[position];
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
