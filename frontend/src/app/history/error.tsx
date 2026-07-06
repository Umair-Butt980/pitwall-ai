"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";

export default function HistoryError({
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
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-10 text-center">
        <p className="font-medium text-sm">Couldn&apos;t render the prediction history</p>
        <button
          onClick={() => unstable_retry()}
          className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
