"use client";

import { useEffect, useReducer } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchCircuitHistory, type CircuitWinner } from "@/lib/api";

interface State {
  loading: boolean;
  winners: CircuitWinner[];
}
type Action =
  | { type: "LOAD" }
  | { type: "OK"; winners: CircuitWinner[] }
  | { type: "FAIL" };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "LOAD": return { loading: true, winners: [] };
    case "OK":   return { loading: false, winners: action.winners };
    case "FAIL": return { loading: false, winners: [] };
    default:     return state;
  }
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  circuitId: string;
  raceName: string;
}

export default function CircuitHistoryPanel({
  open,
  onOpenChange,
  circuitId,
  raceName,
}: Props) {
  const [{ loading, winners }, dispatch] = useReducer(reducer, {
    loading: false,
    winners: [],
  });

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    dispatch({ type: "LOAD" });
    fetchCircuitHistory(circuitId)
      .then((data) => {
        if (!cancelled)
          dispatch({ type: "OK", winners: [...data].reverse() });
      })
      .catch(() => {
        if (!cancelled) dispatch({ type: "FAIL" });
      });
    return () => { cancelled = true; };
  }, [open, circuitId]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col overflow-y-auto sm:max-w-lg">
        <SheetHeader className="px-6 pt-6 pb-4 border-b border-border/50">
          <SheetTitle>Circuit History</SheetTitle>
          <SheetDescription>{raceName}</SheetDescription>
        </SheetHeader>

        <div className="px-6 py-4">
          {loading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : winners.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No historical data found.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">Year</TableHead>
                  <TableHead>Winner</TableHead>
                  <TableHead>Constructor</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {winners.map((w) => (
                  <TableRow key={w.year}>
                    <TableCell className="font-mono text-sm">{w.year}</TableCell>
                    <TableCell className="font-medium text-sm">{w.winner}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {w.constructor}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
