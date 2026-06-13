"use client";

import { useState, useTransition } from "react";
import { useParams } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { fetchDriverStats, type DriverStats } from "@/lib/api";

// Popular circuit IDs — the full list would come from /api/races
const CIRCUITS = [
  { id: "bahrain", label: "Bahrain" },
  { id: "jeddah", label: "Saudi Arabia" },
  { id: "albert_park", label: "Australia" },
  { id: "suzuka", label: "Japan" },
  { id: "shanghai", label: "China" },
  { id: "miami", label: "Miami" },
  { id: "imola", label: "Emilia Romagna" },
  { id: "monaco", label: "Monaco" },
  { id: "villeneuve", label: "Canada" },
  { id: "catalunya", label: "Spain" },
  { id: "red_bull_ring", label: "Austria" },
  { id: "silverstone", label: "Britain" },
  { id: "hungaroring", label: "Hungary" },
  { id: "spa", label: "Belgium" },
  { id: "zandvoort", label: "Netherlands" },
  { id: "monza", label: "Italy" },
  { id: "baku", label: "Azerbaijan" },
  { id: "marina_bay", label: "Singapore" },
  { id: "americas", label: "USA (Austin)" },
  { id: "rodriguez", label: "Mexico" },
  { id: "interlagos", label: "Brazil" },
  { id: "vegas", label: "Las Vegas" },
  { id: "yas_marina", label: "Abu Dhabi" },
];

export default function DriverDetailPage() {
  const { driverId } = useParams<{ driverId: string }>();
  const [circuit, setCircuit] = useState("");
  const [stats, setStats] = useState<DriverStats | null>(null);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  function handleCircuitChange(val: string) {
    setCircuit(val);
    setError("");
    startTransition(async () => {
      try {
        const data = await fetchDriverStats(driverId, val);
        setStats(data);
      } catch {
        setStats(null);
        setError("No data found for this combination.");
      }
    });
  }

  const displayId = driverId.replace(/_/g, " ");

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <h1 className="mb-1 text-2xl font-bold capitalize">{displayId}</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Circuit-by-circuit stats
      </p>

      <div className="mb-6">
        <Select onValueChange={handleCircuitChange} value={circuit}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Select a circuit" />
          </SelectTrigger>
          <SelectContent>
            {CIRCUITS.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isPending && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {!isPending && error && (
        <p className="text-sm text-muted-foreground">{error}</p>
      )}

      {!isPending && stats && (
        <div className="flex flex-col gap-6">
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Starts", value: stats.starts },
              { label: "Wins", value: stats.wins },
              { label: "Podiums", value: stats.podiums },
              { label: "Best Finish", value: stats.best_finish ?? "—" },
            ].map(({ label, value }) => (
              <Card key={label} className="border-border/50">
                <CardHeader className="pb-1 pt-3 px-4">
                  <CardTitle className="text-xs text-muted-foreground font-normal">
                    {label}
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-3">
                  <p className="text-2xl font-bold">{value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Results table */}
          <div>
            <h2 className="mb-3 text-sm font-medium uppercase tracking-widest text-muted-foreground">
              Race Results
            </h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">Year</TableHead>
                  <TableHead className="w-16">Grid</TableHead>
                  <TableHead className="w-16">Finish</TableHead>
                  <TableHead className="w-16">Points</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...stats.results].reverse().map((r, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono text-sm">{r.year}</TableCell>
                    <TableCell className="text-muted-foreground">{r.grid}</TableCell>
                    <TableCell>
                      <Badge
                        variant={r.position <= 3 ? "default" : "secondary"}
                        className="text-xs"
                      >
                        P{r.position}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono">{r.points}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {r.status ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {!isPending && !stats && !error && (
        <p className="text-sm text-muted-foreground">
          Select a circuit above to view stats.
        </p>
      )}
    </div>
  );
}
