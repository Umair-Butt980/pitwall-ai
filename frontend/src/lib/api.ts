// The browser talks to the backend directly, so this must be a host-reachable
// URL (localhost:8000), not the docker-internal hostname (http://backend:8000).
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface HealthStatus {
  status: "ok" | "degraded";
  mongo: "ok" | "down";
  redis: "ok" | "down";
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}
