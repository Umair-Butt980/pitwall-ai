"use client";

import { useEffect, useState } from "react";
import {
  fetchLiveSession,
  fetchTrackOutline,
  fetchLiveMap,
  type LiveSession,
  type TrackPoint,
  type LiveCar,
} from "@/lib/api";
import TrackMap from "./TrackMap";
import SessionStateBanner from "./SessionStateBanner";

// Start the replay where the field is spread out on track (not the grid/formation),
// so the first frame is immediately legible.
const START_OFFSET_SECONDS = 1800;

function atTimestamp(session: LiveSession, elapsed: number): string {
  const start = new Date(session.date_start ?? "").getTime();
  // "YYYY-MM-DDTHH:MM:SS" (tz-naive UTC — matches what the backend expects)
  return new Date(start + elapsed * 1000).toISOString().slice(0, 19);
}

function durationSeconds(session: LiveSession): number {
  const start = new Date(session.date_start ?? "").getTime();
  const end = new Date(session.date_end ?? "").getTime();
  return Number.isFinite(start) && Number.isFinite(end) ? (end - start) / 1000 : Infinity;
}

export default function LiveRaceCenter({ sessionKey }: { sessionKey?: number }) {
  const [session, setSession] = useState<LiveSession | null>(null);
  const [outline, setOutline] = useState<TrackPoint[]>([]);
  const [cars, setCars] = useState<LiveCar[]>([]);
  const [elapsed, setElapsed] = useState(START_OFFSET_SECONDS);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(2);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // 1. Resolve the session + fetch the (static) track outline once.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchLiveSession(sessionKey)
      .then(async (s) => {
        if (cancelled) return;
        setSession(s);
        setElapsed(START_OFFSET_SECONDS);
        const outlineData = await fetchTrackOutline(s.session_key);
        if (!cancelled) {
          setOutline(outlineData.points);
          setLoading(false);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e.message ?? "Failed to load session");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sessionKey]);

  // 2. Replay clock — advance the elapsed time while playing; stop at session end.
  useEffect(() => {
    if (!playing || !session) return;
    const total = durationSeconds(session);
    const id = setInterval(() => {
      setElapsed((e) => {
        const next = e + speed;
        if (next >= total) {
          setPlaying(false);
          return total;
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [playing, speed, session]);

  // 3. Fetch car positions for the current `at`. Guards against out-of-order responses.
  useEffect(() => {
    if (!session || outline.length === 0) return;
    let cancelled = false;
    fetchLiveMap(session.session_key, atTimestamp(session, elapsed))
      .then((m) => {
        if (!cancelled) setCars(m.cars);
      })
      .catch(() => {
        /* transient — keep the last frame */
      });
    return () => {
      cancelled = true;
    };
  }, [session, elapsed, outline.length]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Live Race Center</h1>
        <p className="text-sm text-muted-foreground">
          Cars plotted live on track from OpenF1 positional data.
        </p>
      </div>

      {loading && (
        <div className="flex h-64 items-center justify-center rounded-lg border border-border/50 bg-card/30">
          <p className="text-sm text-muted-foreground">Loading session…</p>
        </div>
      )}

      {error && !loading && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-6 text-center">
          <p className="font-medium text-sm">Couldn&apos;t load the live session</p>
          <p className="mt-1 font-mono text-xs text-destructive">{error}</p>
        </div>
      )}

      {session && !loading && !error && (
        <>
          <SessionStateBanner
            session={session}
            playing={playing}
            speed={speed}
            elapsed={elapsed}
            onTogglePlay={() => setPlaying((p) => !p)}
            onRestart={() => {
              setElapsed(START_OFFSET_SECONDS);
              setPlaying(true);
            }}
            onSpeed={setSpeed}
          />

          <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
            <div className="rounded-xl border border-border/50 bg-card/30 p-3">
              <TrackMap outline={outline} cars={cars} />
            </div>

            <aside className="flex flex-col gap-3 rounded-xl border border-border/50 bg-card/30 p-4">
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                On Track · {cars.length} cars
              </p>
              <ul className="flex flex-col gap-1.5">
                {[...cars]
                  .sort((a, b) => a.code.localeCompare(b.code))
                  .map((c) => (
                    <li key={c.num} className="flex items-center gap-2 text-sm">
                      <span
                        className="h-3 w-3 shrink-0 rounded-full"
                        style={{ backgroundColor: c.colour }}
                      />
                      <span className="font-mono">{c.code}</span>
                    </li>
                  ))}
              </ul>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                Timing tower, race control, and the AI prediction-vs-reality overlay
                land in the next round.
              </p>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
