"use client";

import { useEffect, useState } from "react";
import { fetchRaces, type Race } from "@/lib/api";
import RaceCard from "@/components/RaceCard";
import NextRaceHero from "@/components/NextRaceHero";
import ChampionshipPulse from "@/components/dashboard/ChampionshipPulse";
import AiScorecard from "@/components/dashboard/AiScorecard";
import LatestPrediction from "@/components/dashboard/LatestPrediction";
import SeasonProgress from "@/components/dashboard/SeasonProgress";
import { Skeleton } from "@/components/ui/skeleton";

function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <Skeleton className="mb-4 h-32 w-full rounded-xl" />
      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-64 w-full rounded-xl" />
        ))}
      </div>
      <Skeleton className="mb-6 h-40 w-full rounded-xl" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-44 w-full rounded-xl" />
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const [races, setRaces] = useState<Race[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const year = new Date().getFullYear();
    fetchRaces(year)
      .then(setRaces)
      .catch(() => setRaces([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <DashboardSkeleton />;

  const now = new Date();
  const nextRace = races.find((r) => new Date(r.date) >= now) ?? null;

  return (
    <>
      {nextRace && <NextRaceHero race={nextRace} />}

      {/* Dashboard widget grid — "mission control" at a glance. */}
      <section className="mx-auto max-w-7xl px-4 pb-4 sm:px-6">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <ChampionshipPulse />
          <AiScorecard />
          <LatestPrediction />
        </div>
        <div className="mt-4">
          <SeasonProgress races={races} />
        </div>
      </section>

      {/* Full season calendar. */}
      <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6">
        <h2 className="mb-4 text-sm font-medium uppercase tracking-widest text-muted-foreground">
          Full Calendar · {races[0]?.year ?? new Date().getFullYear()} Season ·{" "}
          {races.length} Races
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {races.map((race) => (
            <RaceCard key={race.round} race={race} />
          ))}
        </div>
      </section>
    </>
  );
}
