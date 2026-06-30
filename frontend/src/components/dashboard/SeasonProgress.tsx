"use client";

import { CalendarDays } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Race } from "@/lib/api";

// Where we are in the season + the next few races. Driven by the race list the
// home page already loads, so it takes `races` as a prop (no extra fetch).
export default function SeasonProgress({ races }: { races: Race[] }) {
  if (races.length === 0) return null;

  const now = new Date();
  const total = races.length;
  const completed = races.filter((r) => new Date(r.date) < now).length;
  const upcoming = races.filter((r) => new Date(r.date) >= now).slice(0, 3);
  const currentRound = Math.min(completed + 1, total);

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium uppercase tracking-widest text-muted-foreground">
          <CalendarDays className="h-4 w-4 text-primary" />
          Season Progress
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-2xl font-bold">
              Round {currentRound}
              <span className="text-base font-normal text-muted-foreground">
                {" "}
                / {total}
              </span>
            </span>
            <span className="text-xs text-muted-foreground">
              {completed} run · {total - completed} to go
            </span>
          </div>
          <Progress value={(completed / total) * 100} className="h-2" />
        </div>

        {upcoming.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground/70">
              Up next
            </p>
            {upcoming.map((r) => (
              <div
                key={r.round}
                className="flex items-center justify-between text-sm"
              >
                <span className="flex items-center gap-2 truncate">
                  <span className="font-mono text-xs text-muted-foreground">
                    R{r.round}
                  </span>
                  <span className="truncate">{r.name}</span>
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {new Date(r.date).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
