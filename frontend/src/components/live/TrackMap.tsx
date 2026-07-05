"use client";

import { type LiveCar, type TrackPoint } from "@/lib/api";

const VIEWBOX = 1000;
const PADDING = 55;

// Cars and the outline are plotted from the SAME bounds (derived from the outline)
// so the dots always sit on the track. F1 `y` grows opposite to SVG `y`, so flip it.
export default function TrackMap({
  outline,
  cars,
}: {
  outline: TrackPoint[];
  cars: LiveCar[];
}) {
  if (outline.length === 0) return null;

  const xs = outline.map((p) => p.x);
  const ys = outline.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const scale = Math.min((VIEWBOX - 2 * PADDING) / spanX, (VIEWBOX - 2 * PADDING) / spanY);
  const offX = (VIEWBOX - spanX * scale) / 2;
  const offY = (VIEWBOX - spanY * scale) / 2;

  const nx = (x: number) => offX + (x - minX) * scale;
  const ny = (y: number) => offY + (maxY - y) * scale; // flip Y

  const polyline = outline
    .map((p) => `${nx(p.x).toFixed(1)},${ny(p.y).toFixed(1)}`)
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`}
      className="h-auto w-full text-muted-foreground"
      role="img"
      aria-label="Live track map"
    >
      <polyline
        points={polyline}
        fill="none"
        stroke="currentColor"
        strokeOpacity={0.28}
        strokeWidth={11}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {cars.map((c) => (
        <g
          key={c.num}
          style={{
            transform: `translate(${nx(c.x).toFixed(1)}px, ${ny(c.y).toFixed(1)}px)`,
            transition: "transform 0.9s linear",
          }}
        >
          <circle r={14} fill={c.colour} stroke="black" strokeWidth={2} />
          <text
            textAnchor="middle"
            y={4}
            fontSize={11}
            fontWeight={700}
            fill="white"
            style={{ pointerEvents: "none" }}
          >
            {c.code}
          </text>
        </g>
      ))}
    </svg>
  );
}
