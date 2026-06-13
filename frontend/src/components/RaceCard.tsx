"use client";

import { useState } from "react";
import { MapPin, Calendar, Flag } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import CircuitHistoryPanel from "@/components/CircuitHistoryPanel";
import PredictSheet from "@/components/PredictSheet";
import type { Race } from "@/lib/api";

function isPast(dateStr: string) {
  return new Date(dateStr) < new Date();
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function RaceCard({ race }: { race: Race }) {
  const past = isPast(race.date);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [predictOpen, setPredictOpen] = useState(false);

  return (
    <>
      <Card
        className={`flex flex-col gap-0 overflow-hidden transition-colors ${
          !past ? "border-primary/30 bg-card" : "border-border/50 opacity-80"
        }`}
      >
        {/* Round badge strip */}
        <div
          className={`flex items-center justify-between px-4 py-2 text-xs font-mono ${
            past ? "bg-muted/30" : "bg-primary/10"
          }`}
        >
          <span className={past ? "text-muted-foreground" : "text-primary font-semibold"}>
            Round {race.round}
          </span>
          <Badge
            variant={past ? "secondary" : "default"}
            className="text-xs"
          >
            {past ? "Past" : "Upcoming"}
          </Badge>
        </div>

        <CardHeader className="px-4 pt-3 pb-1 gap-1">
          <h3 className="font-semibold text-sm leading-tight line-clamp-2">{race.name}</h3>
          <p className="text-xs text-muted-foreground">{race.circuit}</p>
        </CardHeader>

        <CardContent className="flex flex-col gap-3 px-4 pb-4 pt-1">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <MapPin className="h-3 w-3 shrink-0" />
              <span>{race.location}, {race.country}</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Calendar className="h-3 w-3 shrink-0" />
              <span>{formatDate(race.date)}</span>
            </div>
          </div>

          <Separator />

          {past ? (
            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs"
              onClick={() => setHistoryOpen(true)}
            >
              <Flag className="h-3 w-3 mr-1" />
              Circuit History
            </Button>
          ) : (
            <Button
              size="sm"
              className="w-full text-xs"
              onClick={() => setPredictOpen(true)}
            >
              🏎️ Predict the Winner
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Past race: circuit history side panel */}
      <CircuitHistoryPanel
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        circuitId={race.circuit_id}
        raceName={race.name}
      />

      {/* Upcoming race: AI prediction sheet */}
      <PredictSheet
        open={predictOpen}
        onOpenChange={setPredictOpen}
        race={race.name}
        year={race.year}
      />
    </>
  );
}
