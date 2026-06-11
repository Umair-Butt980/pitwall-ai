"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchHealth, type HealthStatus } from "@/lib/api";

type Service = { name: string; state: "ok" | "down" | "unknown" };

function StatusBadge({ state }: { state: Service["state"] }) {
  if (state === "ok") {
    return (
      <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30">
        ● Online
      </Badge>
    );
  }
  if (state === "down") {
    return (
      <Badge className="bg-red-500/15 text-red-400 border-red-500/30">
        ● Down
      </Badge>
    );
  }
  return (
    <Badge className="bg-zinc-500/15 text-zinc-400 border-zinc-500/30">
      ● Checking…
    </Badge>
  );
}

export default function Home() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [backendUp, setBackendUp] = useState<Service["state"]>("unknown");

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const data = await fetchHealth();
        if (!active) return;
        setHealth(data);
        setBackendUp("ok");
      } catch {
        if (!active) return;
        setHealth(null);
        setBackendUp("down");
      }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const services: Service[] = [
    { name: "FastAPI Backend", state: backendUp },
    { name: "MongoDB Atlas", state: health?.mongo ?? "unknown" },
    { name: "Redis Cache", state: health?.redis ?? "unknown" },
  ];

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10 bg-zinc-950 px-6">
      <div className="text-center">
        <p className="mb-3 font-mono text-sm tracking-[0.3em] text-red-500">
          PITWALL AI
        </p>
        <h1 className="text-4xl font-bold tracking-tight text-zinc-50 sm:text-5xl">
          F1 Race Prediction,
          <br />
          <span className="text-red-500">powered by AI agents</span>
        </h1>
        <p className="mx-auto mt-4 max-w-md text-zinc-400">
          Six specialized LangGraph agents analyze weather, drivers, cars,
          circuits and strategy to predict the podium — with reasoning.
        </p>
      </div>

      <Card className="w-full max-w-md border-zinc-800 bg-zinc-900/60">
        <CardHeader>
          <CardTitle className="text-zinc-100">System Status</CardTitle>
          <CardDescription>
            Live health of the platform services
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {services.map((s) => (
            <div
              key={s.name}
              className="flex items-center justify-between rounded-md border border-zinc-800 bg-zinc-950/50 px-4 py-3"
            >
              <span className="font-mono text-sm text-zinc-300">{s.name}</span>
              <StatusBadge state={s.state} />
            </div>
          ))}
        </CardContent>
      </Card>

      <p className="font-mono text-xs text-zinc-600">
        Phase 1 — Foundation · Docker Compose · FastAPI · Next.js
      </p>
    </main>
  );
}
