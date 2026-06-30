"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchDriverStandings,
  fetchConstructorStandings,
  type DriverStanding,
  type ConstructorStanding,
} from "@/lib/api";

// Top-3 drivers + constructors with the gap to the championship leader — the
// "who's winning right now" glance for the dashboard.
export default function ChampionshipPulse() {
  const [drivers, setDrivers] = useState<DriverStanding[] | null>(null);
  const [teams, setTeams] = useState<ConstructorStanding[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const year = new Date().getFullYear();
    Promise.all([fetchDriverStandings(year), fetchConstructorStandings(year)])
      .then(([d, c]) => {
        setDrivers(d.slice(0, 3));
        setTeams(c.slice(0, 3));
      })
      .catch(() => setFailed(true));
  }, []);

  const loading = !failed && (drivers === null || teams === null);

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium uppercase tracking-widest text-muted-foreground">
          <Trophy className="h-4 w-4 text-primary" />
          Championship Pulse
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loading ? (
          <Skeleton className="h-40 w-full" />
        ) : failed || !drivers?.length ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Standings unavailable.
          </p>
        ) : (
          <>
            <LeaderList
              label="Drivers"
              leaderPts={drivers[0]?.points ?? 0}
              rows={drivers.map((d) => ({
                key: d.driver_id,
                name: d.driver_name,
                sub: d.team,
                points: d.points,
              }))}
            />
            <LeaderList
              label="Constructors"
              leaderPts={teams?.[0]?.points ?? 0}
              rows={(teams ?? []).map((c) => ({
                key: c.constructor_id,
                name: c.constructor_name,
                points: c.points,
              }))}
            />
            <Link
              href="/standings"
              className="text-xs font-medium text-primary hover:underline"
            >
              Full standings →
            </Link>
          </>
        )}
      </CardContent>
    </Card>
  );
}

interface LeaderRow {
  key: string;
  name: string;
  sub?: string;
  points: number;
}

function LeaderList({
  label,
  rows,
  leaderPts,
}: {
  label: string;
  rows: LeaderRow[];
  leaderPts: number;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground/70">
        {label}
      </p>
      {rows.map((r, i) => {
        const gap = leaderPts - r.points;
        return (
          <div key={r.key} className="flex items-center gap-2 text-sm">
            <span className="w-4 font-mono text-xs font-bold text-muted-foreground">
              {i + 1}
            </span>
            <span className="flex-1 truncate font-medium">
              {r.name}
              {r.sub && (
                <span className="ml-1 text-xs text-muted-foreground">{r.sub}</span>
              )}
            </span>
            <span className="font-mono font-semibold">{r.points}</span>
            <span className="w-12 text-right font-mono text-xs text-muted-foreground">
              {i === 0 ? "—" : `-${gap}`}
            </span>
          </div>
        );
      })}
    </div>
  );
}
