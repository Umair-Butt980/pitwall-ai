"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchPredictionHistory,
  type PredictionHistoryItem,
} from "@/lib/api";

const PODIUM_LABEL = ["P1", "P2", "P3"];
const PODIUM_COLOR = [
  "text-yellow-400",
  "text-zinc-300",
  "text-amber-600",
];

// Shows the most recent AI prediction and, if the race has run, whether it hit.
export default function LatestPrediction() {
  const [item, setItem] = useState<PredictionHistoryItem | null>(null);
  const [state, setState] = useState<"loading" | "empty" | "ready">("loading");

  useEffect(() => {
    fetchPredictionHistory()
      .then((items) => {
        if (items.length === 0) {
          setState("empty");
        } else {
          setItem(items[0]);
          setState("ready");
        }
      })
      .catch(() => setState("empty"));
  }, []);

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium uppercase tracking-widest text-muted-foreground">
          <Brain className="h-4 w-4 text-primary" />
          Latest Prediction
        </CardTitle>
      </CardHeader>
      <CardContent>
        {state === "loading" ? (
          <Skeleton className="h-32 w-full" />
        ) : state === "empty" || !item ? (
          <div className="flex flex-col gap-3 py-2">
            <p className="text-sm text-muted-foreground">
              No predictions yet. Pick a race and run the AI to see its podium call
              here.
            </p>
            <Link
              href="/"
              className="text-xs font-medium text-primary hover:underline"
            >
              Predict a race →
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold leading-tight">{item.race}</p>
                <p className="text-xs text-muted-foreground">{item.year}</p>
              </div>
              <GradeBadge item={item} />
            </div>

            <div className="flex flex-col gap-1.5">
              {item.predicted_podium.map((driver, i) => {
                const onPodium =
                  item.actual_podium?.includes(driver) ?? null;
                const exact = item.actual_podium?.[i] === driver;
                return (
                  <div
                    key={driver}
                    className="flex items-center gap-2 rounded-md border border-border/40 px-3 py-1.5 text-sm"
                  >
                    <span
                      className={`w-6 font-mono text-xs font-bold ${PODIUM_COLOR[i]}`}
                    >
                      {PODIUM_LABEL[i]}
                    </span>
                    <span className="flex-1 truncate">{driver}</span>
                    {onPodium !== null && (
                      <span className="text-xs">
                        {exact ? (
                          <span className="text-primary">✓</span>
                        ) : onPodium ? (
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

            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                Confidence{" "}
                <span className="font-semibold text-foreground">
                  {Math.round(item.confidence * 100)}%
                </span>
              </span>
              <Link
                href="/history"
                className="text-xs font-medium text-primary hover:underline"
              >
                History →
              </Link>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GradeBadge({ item }: { item: PredictionHistoryItem }) {
  if (item.was_correct === null) {
    return (
      <Badge variant="secondary" className="text-xs">
        Pending
      </Badge>
    );
  }
  return item.was_correct ? (
    <Badge className="bg-primary text-primary-foreground text-xs">✓ Winner</Badge>
  ) : (
    <Badge variant="outline" className="border-border text-xs text-muted-foreground">
      ✗ Missed
    </Badge>
  );
}
