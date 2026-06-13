import { Suspense } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchDriverStandings,
  fetchConstructorStandings,
  type DriverStanding,
  type ConstructorStanding,
} from "@/lib/api";

async function StandingsData() {
  const year = new Date().getFullYear();
  const [drivers, constructors] = await Promise.all([
    fetchDriverStandings(year),
    fetchConstructorStandings(year),
  ]);

  const maxDriverPts = drivers[0]?.points ?? 1;
  const maxConstructorPts = constructors[0]?.points ?? 1;

  return (
    <Tabs defaultValue="drivers">
      <TabsList className="mb-6">
        <TabsTrigger value="drivers">Drivers</TabsTrigger>
        <TabsTrigger value="constructors">Constructors</TabsTrigger>
      </TabsList>

      {/* Drivers */}
      <TabsContent value="drivers">
        {drivers.length === 0 ? (
          <EmptyStandings label="driver standings" year={year} />
        ) : (
          <DriverTable drivers={drivers} maxPts={maxDriverPts} />
        )}
      </TabsContent>

      {/* Constructors */}
      <TabsContent value="constructors">
        {constructors.length === 0 ? (
          <EmptyStandings label="constructor standings" year={year} />
        ) : (
          <ConstructorTable constructors={constructors} maxPts={maxConstructorPts} />
        )}
      </TabsContent>
    </Tabs>
  );
}

function DriverTable({
  drivers,
  maxPts,
}: {
  drivers: DriverStanding[];
  maxPts: number;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">Pos</TableHead>
          <TableHead>Driver</TableHead>
          <TableHead className="hidden sm:table-cell">Team</TableHead>
          <TableHead className="w-16 text-right">Pts</TableHead>
          <TableHead className="w-12 text-right hidden sm:table-cell">Wins</TableHead>
          <TableHead className="hidden md:table-cell w-40">Points share</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {drivers.map((d) => (
          <TableRow key={d.driver_id}>
            <TableCell className="font-mono font-bold text-sm">{d.position}</TableCell>
            <TableCell className="font-medium">{d.driver_name}</TableCell>
            <TableCell className="text-muted-foreground hidden sm:table-cell">
              {d.team}
            </TableCell>
            <TableCell className="text-right font-mono font-semibold">{d.points}</TableCell>
            <TableCell className="text-right text-muted-foreground hidden sm:table-cell">
              {d.wins}
            </TableCell>
            <TableCell className="hidden md:table-cell">
              <Progress
                value={(d.points / maxPts) * 100}
                className="h-1.5"
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ConstructorTable({
  constructors,
  maxPts,
}: {
  constructors: ConstructorStanding[];
  maxPts: number;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">Pos</TableHead>
          <TableHead>Constructor</TableHead>
          <TableHead className="w-16 text-right">Pts</TableHead>
          <TableHead className="w-12 text-right hidden sm:table-cell">Wins</TableHead>
          <TableHead className="hidden md:table-cell w-40">Points share</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {constructors.map((c) => (
          <TableRow key={c.constructor_id}>
            <TableCell className="font-mono font-bold text-sm">{c.position}</TableCell>
            <TableCell className="font-medium">{c.constructor_name}</TableCell>
            <TableCell className="text-right font-mono font-semibold">{c.points}</TableCell>
            <TableCell className="text-right text-muted-foreground hidden sm:table-cell">
              {c.wins}
            </TableCell>
            <TableCell className="hidden md:table-cell">
              <Progress
                value={(c.points / maxPts) * 100}
                className="h-1.5"
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function EmptyStandings({ label, year }: { label: string; year: number }) {
  return (
    <p className="py-12 text-center text-sm text-muted-foreground">
      No {label} available for {year} yet.
    </p>
  );
}

function StandingsSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-10 w-48" />
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

export default function StandingsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <h1 className="mb-6 text-2xl font-bold">Championship Standings</h1>
      <Suspense fallback={<StandingsSkeleton />}>
        <StandingsData />
      </Suspense>
    </div>
  );
}
