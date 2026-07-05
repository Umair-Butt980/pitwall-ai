from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from services import openf1_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live"])

# 2024 Interlagos (Brazil) — wet, red-flagged, multiple safety cars, Verstappen won
# from P17. A reliable, dramatic replay so /live is always demoable off a race day.
DEMO_SESSION_KEY = 9636

# How far back from `at` to look for each car's most recent position sample.
_MAP_WINDOW_SECONDS = 4


# ─── datetime helpers ────────────────────────────────────────────────────────
# OpenF1's date filters (`date>=`, `date<=`) are safest as tz-naive UTC strings
# (a literal "+00:00" offset can be misread as a space in a URL query), so we
# normalise every timestamp to "YYYY-MM-DDTHH:MM:SS" before querying.

def _parse(iso: str | None) -> datetime | None:
    if not iso:
        return None
    dt = datetime.fromisoformat(iso)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _openf1_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ─── Session state resolver ──────────────────────────────────────────────────

def _session_payload(mode: str, meta: dict) -> dict:
    return {
        "mode": mode,
        "session_key": meta.get("session_key"),
        "meeting_name": meta.get("meeting_name"),
        "session_name": meta.get("session_name"),
        "circuit_short_name": meta.get("circuit_short_name"),
        "country_name": meta.get("country_name"),
        "date_start": meta.get("date_start"),
        "date_end": meta.get("date_end"),
        "year": meta.get("year"),
    }


@router.get("/session")
async def live_session(session_key: int | None = None) -> dict:
    """Resolve which session the Live Race Center should show.

    Replay-first (this round): with no override we return a reliable dramatic race
    so the page is always demoable. Passing ?session_key= replays any session and
    marks it "live" if its window contains now. (Live auto-detection + the
    no-session countdown state come in the next round.)
    """
    if session_key is None:
        meta = await openf1_service.get_session_meta(DEMO_SESSION_KEY)
        if not meta:
            raise HTTPException(status_code=502, detail="Demo session unavailable from OpenF1")
        return _session_payload("replay", meta)

    meta = await openf1_service.get_session_meta(session_key)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Session {session_key} not found")

    now = datetime.now(timezone.utc)
    start, end = _parse(meta.get("date_start")), _parse(meta.get("date_end"))
    is_live = bool(start and end and start <= now <= end)
    return _session_payload("live" if is_live else "replay", meta)


# ─── Track outline ───────────────────────────────────────────────────────────

def _pick_green_lap(laps: list[dict]) -> dict | None:
    """A representative flat-out lap (median duration) — avoids pit/SC/out laps."""
    cand = [
        lap for lap in laps
        if lap.get("lap_duration")
        and lap.get("date_start")
        and not lap.get("is_pit_out_lap")
    ]
    if not cand:
        return None
    cand.sort(key=lambda lap: lap["lap_duration"])
    return cand[len(cand) // 2]


def _downsample(points: list[dict], cap: int) -> list[dict]:
    if len(points) <= cap:
        return points
    step = len(points) / cap
    return [points[int(i * step)] for i in range(cap)]


async def _circuit_outline(session_key: int) -> list[dict]:
    """Trace the circuit shape from one driver's clean lap of /location points.

    OpenF1 gives car coordinates but no track shape, so we derive it: take a
    representative green lap for a driver and return its ordered x/y path. Static
    per circuit; the underlying OpenF1 calls are cached.
    """
    drivers = await openf1_service.get_drivers(session_key)
    for d in drivers:
        num = d.get("driver_number")
        if num is None:
            continue
        laps = await openf1_service.get_laps(session_key, num)
        lap = _pick_green_lap(laps)
        if not lap:
            continue
        start = _parse(lap["date_start"])
        end = start + timedelta(seconds=lap["lap_duration"] + 1)
        loc = await openf1_service.get_location(
            session_key, driver_number=num,
            date_gte=_openf1_ts(start), date_lte=_openf1_ts(end),
        )
        pts = [
            {"x": r["x"], "y": r["y"]}
            for r in sorted(loc, key=lambda r: r.get("date") or "")
            if r.get("x") is not None and not (r["x"] == 0 and r["y"] == 0)
        ]
        if len(pts) >= 40:
            return _downsample(pts, 300)
    return []


@router.get("/track")
async def live_track(session_key: int) -> dict:
    """Circuit outline points (raw x/y) for the given session's track map."""
    points = await _circuit_outline(session_key)
    if not points:
        raise HTTPException(status_code=404, detail="No location data to derive a track outline")
    return {"session_key": session_key, "points": points}


# ─── Live/replay car positions ───────────────────────────────────────────────

@router.get("/map")
async def live_map(session_key: int, at: str) -> dict:
    """Every car's most recent x/y at timestamp `at` (raw coords; client normalises).

    `at` is an ISO timestamp the client advances on the replay clock. We fetch a
    short window ending at `at` and keep each driver's latest sample.
    """
    at_dt = _parse(at)
    if at_dt is None:
        raise HTTPException(status_code=400, detail="Invalid `at` timestamp")
    lo = at_dt - timedelta(seconds=_MAP_WINDOW_SECONDS)

    loc = await openf1_service.get_location(
        session_key, date_gte=_openf1_ts(lo), date_lte=_openf1_ts(at_dt)
    )
    drivers = await openf1_service.get_drivers(session_key)
    meta = {d.get("driver_number"): d for d in drivers}

    latest: dict[int, dict] = {}
    for r in loc:
        num = r.get("driver_number")
        if num is None or r.get("x") is None:
            continue
        if num not in latest or (r.get("date") or "") > (latest[num].get("date") or ""):
            latest[num] = r

    cars = []
    for num, r in latest.items():
        if r["x"] == 0 and r["y"] == 0:
            continue
        d = meta.get(num, {})
        colour = d.get("team_colour")
        cars.append({
            "num": num,
            "code": d.get("name_acronym") or str(num),
            "colour": f"#{colour}" if colour else "#9ca3af",
            "x": r["x"],
            "y": r["y"],
        })

    return {"at": at, "cars": cars}
