"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";

export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 px-4 py-24 text-center sm:px-6">
      <p className="text-4xl">🏁</p>
      <h2 className="text-xl font-bold tracking-tight">Something went wrong</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        An unexpected error stopped this page from rendering.
        {error.digest && (
          <span className="mt-1 block font-mono text-xs">Ref: {error.digest}</span>
        )}
      </p>
      <button
        onClick={() => unstable_retry()}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}
