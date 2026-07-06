export default function Loading() {
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6 sm:px-6">
      <div className="h-8 w-64 animate-pulse rounded-md bg-muted/40" />
      <div className="h-4 w-96 animate-pulse rounded-md bg-muted/30" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse rounded-xl bg-muted/20" />
        ))}
      </div>
    </div>
  );
}
