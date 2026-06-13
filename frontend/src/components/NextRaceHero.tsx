"use client";

import { useEffect, useMemo, useState } from "react";
import { MapPin, Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Race } from "@/lib/api";

function formatCountdown(ms: number) {
  if (ms <= 0) return "Race day!";
  const d = Math.floor(ms / 86400000);
  const h = Math.floor((ms % 86400000) / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  return `${h}h ${m}m ${s}s`;
}

export default function NextRaceHero({ race }: { race: Race }) {
  const raceDate = useMemo(() => new Date(race.date), [race.date]);
  const raceTs = raceDate.getTime();
  const [remaining, setRemaining] = useState(() => raceTs - Date.now());

  useEffect(() => {
    const id = setInterval(() => {
      setRemaining(raceTs - Date.now());
    }, 1000);
    return () => clearInterval(id);
  }, [raceTs]);

  return (
    <section className="mx-auto max-w-7xl px-4 pt-6 pb-4 sm:px-6">
      <Card className="border-primary/30 bg-primary/5">
        <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Badge className="text-xs">Next Race</Badge>
              <span className="font-mono text-xs text-muted-foreground">
                Round {race.round}
              </span>
            </div>
            <h2 className="text-lg font-bold">{race.name}</h2>
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <MapPin className="h-3.5 w-3.5" />
              <span>{race.circuit} · {race.location}, {race.country}</span>
            </div>
          </div>

          <div className="flex flex-col items-start gap-1 sm:items-end">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span>
                {raceDate.toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })}
              </span>
            </div>
            <span className="font-mono text-2xl font-bold text-primary">
              {formatCountdown(remaining)}
            </span>
            <span className="text-xs text-muted-foreground">until race start</span>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
