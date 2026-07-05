import LiveRaceCenter from "@/components/live/LiveRaceCenter";

// Optional ?session=<session_key> forces a specific replay; otherwise the backend
// resolves a reliable demo session.
export default async function LivePage({
  searchParams,
}: {
  searchParams: Promise<{ session?: string }>;
}) {
  const { session } = await searchParams;
  const sessionKey = session ? Number(session) : undefined;
  return <LiveRaceCenter sessionKey={Number.isFinite(sessionKey) ? sessionKey : undefined} />;
}
