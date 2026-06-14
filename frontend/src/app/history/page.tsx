"use client";

import { useEffect, useReducer } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  fetchPredictionHistory,
  type PredictionHistoryItem,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ─── Reducer for row expansion ────────────────────────────────────────────────

type ExpandAction = { type: "TOGGLE"; id: string } | { type: "LOADED" };
interface PageState {
  items: PredictionHistoryItem[];
  loading: boolean;
  expanded: Set<string>;
}

function pageReducer(state: PageState, action: ExpandAction & { items?: PredictionHistoryItem[] }): PageState {
  switch (action.type) {
    case "LOADED":
      return { ...state, loading: false, items: action.items ?? [] };
    case "TOGGLE": {
      const next = new Set(state.expanded);
      if (next.has(action.id)) next.delete(action.id);
      else next.add(action.id);
      return { ...state, expanded: next };
    }
    default:
      return state;
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function podiumLabel(i: number) {
  return ["P1", "P2", "P3"][i] ?? `P${i + 1}`;
}

const POSITIONS = [0, 1, 2] as const;

// ─── Summary cards ────────────────────────────────────────────────────────────

function AccuracySummary({ items }: { items: PredictionHistoryItem[] }) {
  const graded = items.filter((i) => i.was_correct !== null);
  if (graded.length === 0) return null;

  const winnersCorrect = graded.filter((i) => i.was_correct).length;
  const totalPodiumHits = graded.reduce(
    (sum, i) => sum + (i.podium_correct_count ?? 0),
    0
  );
  const podiumAccuracyPct = Math.round(
    (totalPodiumHits / (graded.length * 3)) * 100
  );

  return (
    <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Card>
        <CardContent className="pt-5">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Winner Correct
          </p>
          <p className="mt-1 text-2xl font-bold">
            {winnersCorrect}
            <span className="text-base font-normal text-muted-foreground">
              /{graded.length}
            </span>
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-5">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Podium Accuracy
          </p>
          <p className="mt-1 text-2xl font-bold">
            {podiumAccuracyPct}
            <span className="text-base font-normal text-muted-foreground">%</span>
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-5">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Avg Podium Hits
          </p>
          <p className="mt-1 text-2xl font-bold">
            {(totalPodiumHits / graded.length).toFixed(1)}
            <span className="text-base font-normal text-muted-foreground">/3</span>
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-5">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Races Graded
          </p>
          <p className="mt-1 text-2xl font-bold">
            {graded.length}
            <span className="text-base font-normal text-muted-foreground">
              /{items.length}
            </span>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Expanded podium comparison ───────────────────────────────────────────────

function PodiumComparison({ item }: { item: PredictionHistoryItem }) {
  const actualPodium = item.actual_podium ?? [];
  const predictedPodium = item.predicted_podium ?? [];

  return (
    <div className="grid grid-cols-2 gap-4 px-4 py-4 bg-muted/10 border-t border-border/40">
      {/* Predicted column */}
      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-widest text-muted-foreground">
          Predicted
        </p>
        <div className="flex flex-col gap-1.5">
          {POSITIONS.map((i) => {
            const driver = predictedPodium[i];
            const onActualPodium = driver && actualPodium.includes(driver);
            const exactPosition = driver && actualPodium[i] === driver;
            return (
              <div
                key={i}
                className="flex items-center gap-2 rounded-md border border-border/40 px-3 py-2 text-sm"
              >
                <span className="w-6 shrink-0 font-mono text-xs text-muted-foreground">
                  {podiumLabel(i)}
                </span>
                <span className="flex-1 truncate">{driver ?? "—"}</span>
                {driver && item.actual_podium && (
                  <span className="text-xs shrink-0">
                    {exactPosition ? (
                      <span className="text-primary font-semibold">✓</span>
                    ) : onActualPodium ? (
                      <span className="text-yellow-400">~</span>
                    ) : (
                      <span className="text-muted-foreground/50">✗</span>
                    )}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Actual column */}
      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-widest text-muted-foreground">
          Actual
        </p>
        {actualPodium.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            {POSITIONS.map((i) => {
              const driver = actualPodium[i];
              const predicted = predictedPodium.includes(driver);
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-md border border-border/40 px-3 py-2 text-sm"
                >
                  <span className="w-6 shrink-0 font-mono text-xs text-muted-foreground">
                    {podiumLabel(i)}
                  </span>
                  <span className={`flex-1 truncate ${predicted ? "text-foreground" : "text-muted-foreground"}`}>
                    {driver ?? "—"}
                  </span>
                  {predicted && (
                    <span className="text-xs text-primary shrink-0">✓</span>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex items-center justify-center h-[108px] rounded-md border border-dashed border-border/40">
            <p className="text-xs text-muted-foreground">Race not run yet</p>
          </div>
        )}
      </div>

      {/* Legend */}
      {item.actual_podium && (
        <div className="col-span-2 flex gap-4 text-xs text-muted-foreground">
          <span><span className="text-primary font-semibold">✓</span> exact position</span>
          <span><span className="text-yellow-400">~</span> on podium, wrong spot</span>
          <span><span className="text-muted-foreground/50">✗</span> missed</span>
        </div>
      )}
    </div>
  );
}

// ─── Result badge (summary row) ───────────────────────────────────────────────

function ResultBadge({ item }: { item: PredictionHistoryItem }) {
  if (item.was_correct === null) {
    return <span className="text-xs text-muted-foreground">Race not run yet</span>;
  }
  return item.was_correct ? (
    <Badge className="bg-primary text-primary-foreground">✓ Winner</Badge>
  ) : (
    <Badge variant="outline" className="border-border text-muted-foreground">
      ✗ Missed
    </Badge>
  );
}

// ─── Empty state ─────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <Card className="border-dashed border-border/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <span>🏁</span> No predictions yet
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          Predictions are stored after you click{" "}
          <span className="font-medium text-foreground">
            &ldquo;Predict the Winner&rdquo;
          </span>{" "}
          on any race. Once the race has been run, the actual result is filled in
          here automatically.
        </p>
        <Badge variant="secondary" className="w-fit">
          Make your first prediction from the home page
        </Badge>
      </CardContent>
    </Card>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const [state, dispatch] = useReducer(pageReducer, {
    items: [],
    loading: true,
    expanded: new Set<string>(),
  });

  useEffect(() => {
    fetchPredictionHistory()
      .then((items) => dispatch({ type: "LOADED", items }))
      .catch(() => dispatch({ type: "LOADED", items: [] }));
  }, []);

  const { items, loading, expanded } = state;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <h1 className="mb-2 text-2xl font-bold">Prediction History</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Accuracy of past AI predictions vs actual race results. Click any row to
        see the full podium breakdown.
      </p>

      {loading ? (
        <Skeleton className="h-64 w-full rounded-xl" />
      ) : items.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <AccuracySummary items={items} />
          <Card className="overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Race</TableHead>
                  <TableHead>Predicted Winner</TableHead>
                  <TableHead>Actual Winner</TableHead>
                  <TableHead className="text-center">Result</TableHead>
                  <TableHead className="text-center">Podium</TableHead>
                  <TableHead className="text-right">Conf.</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => {
                  const isOpen = expanded.has(item._id);
                  const isGraded = item.was_correct !== null;
                  return (
                    <>
                      <TableRow
                        key={item._id}
                        className="cursor-pointer hover:bg-muted/30"
                        onClick={() =>
                          dispatch({ type: "TOGGLE", id: item._id })
                        }
                      >
                        <TableCell className="pr-0 text-muted-foreground">
                          {isOpen ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="font-medium">{item.race}</div>
                          <div className="text-xs text-muted-foreground">
                            {item.year}
                          </div>
                        </TableCell>
                        <TableCell>{item.predicted_winner}</TableCell>
                        <TableCell>
                          {item.actual_winner ?? (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          <ResultBadge item={item} />
                        </TableCell>
                        <TableCell className="text-center">
                          {isGraded ? (
                            <span className="text-sm">
                              <span className="font-semibold">
                                {item.podium_correct_count}
                              </span>
                              <span className="text-muted-foreground">/3</span>
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          {Math.round(item.confidence * 100)}%
                        </TableCell>
                      </TableRow>

                      {isOpen && (
                        <TableRow key={`${item._id}-detail`} className="hover:bg-transparent">
                          <TableCell colSpan={7} className="p-0">
                            <PodiumComparison item={item} />
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  );
                })}
              </TableBody>
            </Table>
          </Card>
        </>
      )}
    </div>
  );
}
