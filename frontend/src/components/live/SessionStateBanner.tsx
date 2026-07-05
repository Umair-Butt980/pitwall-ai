"use client";

import { Play, Pause, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { type LiveSession } from "@/lib/api";

const SPEEDS = [1, 2, 4] as const;

function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export default function SessionStateBanner({
  session,
  playing,
  speed,
  elapsed,
  onTogglePlay,
  onRestart,
  onSpeed,
}: {
  session: LiveSession;
  playing: boolean;
  speed: number;
  elapsed: number;
  onTogglePlay: () => void;
  onRestart: () => void;
  onSpeed: (s: number) => void;
}) {
  const isLive = session.mode === "live";
  const title = [session.circuit_short_name, session.country_name]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/50 bg-card/50 px-4 py-3">
      <div className="flex items-center gap-3">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
            isLive
              ? "bg-primary/15 text-primary"
              : "bg-amber-500/15 text-amber-400"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              isLive ? "animate-pulse bg-primary" : "bg-amber-400"
            }`}
          />
          {isLive ? "LIVE" : "REPLAY"}
        </span>
        <div className="leading-tight">
          <p className="text-sm font-medium text-foreground">
            {title || "Session"}
          </p>
          <p className="font-mono text-xs text-muted-foreground">
            {session.session_name} · T+{clock(elapsed)}
            {session.year ? ` · ${session.year}` : ""}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button size="sm" variant="ghost" onClick={onRestart} aria-label="Restart replay">
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button size="sm" variant="secondary" onClick={onTogglePlay}>
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          <span className="ml-1">{playing ? "Pause" : "Play"}</span>
        </Button>
        <div className="flex items-center overflow-hidden rounded-md border border-border/60">
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => onSpeed(s)}
              className={`px-2 py-1 text-xs font-mono ${
                speed === s
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:bg-muted/40"
              }`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
