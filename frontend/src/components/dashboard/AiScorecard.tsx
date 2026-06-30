"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Target } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchPredictionStats, type PredictionStats } from "@/lib/api";

// Headline credibility widget: how often the AI has called the winner / podium.
export default function AiScorecard() {
  const [stats, setStats] = useState<PredictionStats | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchPredictionStats()
      .then(setStats)
      .catch(() => setFailed(true));
  }, []);

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium uppercase tracking-widest text-muted-foreground">
          <Target className="h-4 w-4 text-primary" />
          AI Scorecard
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!stats && !failed ? (
          <Skeleton className="h-28 w-full" />
        ) : failed ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Stats unavailable.
          </p>
        ) : stats!.graded === 0 ? (
          <div className="flex flex-col gap-3 py-2">
            <p className="text-sm text-muted-foreground">
              No graded predictions yet. Accuracy appears here once a predicted
              race has been run.
            </p>
            <Link
              href="/history"
              className="text-xs font-medium text-primary hover:underline"
            >
              View prediction history →
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-end gap-2">
              <span className="font-mono text-4xl font-black text-primary">
                {Math.round(stats!.winner_accuracy * 100)}%
              </span>
              <span className="mb-1 text-xs text-muted-foreground">
                winner accuracy
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <Stat value={`${stats!.winner_correct}/${stats!.graded}`} label="Winners" />
              <Stat value={stats!.avg_podium_hits.toFixed(1)} label="Avg podium /3" />
              <Stat value={String(stats!.total)} label="Predictions" />
            </div>
            <Link
              href="/history"
              className="text-xs font-medium text-primary hover:underline"
            >
              Full accuracy breakdown →
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-border/50 bg-muted/20 py-2">
      <p className="font-mono text-lg font-bold">{value}</p>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
    </div>
  );
}
