"use client";

import { useState } from "react";
import {
  type LucideIcon,
  CheckCircle2,
  Circle,
  ChevronDown,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

export type AgentStatus = "pending" | "running" | "done";

interface Props {
  name: string;
  description: string;
  Icon: LucideIcon;
  status: AgentStatus;
  children?: React.ReactNode; // detail panel, revealed on click once done
}

function Spinner() {
  return (
    <span className="relative flex h-4 w-4 items-center justify-center">
      <span className="absolute inline-flex h-full w-full animate-spin rounded-full border-2 border-transparent border-t-primary" />
    </span>
  );
}

export default function AgentStatusRow({
  name,
  description,
  Icon,
  status,
  children,
}: Props) {
  const [open, setOpen] = useState(false);
  const expandable = status === "done" && Boolean(children);

  return (
    <div className="rounded-lg border border-border/50 bg-card/50">
      <button
        type="button"
        disabled={!expandable}
        onClick={() => expandable && setOpen((o) => !o)}
        className={`flex w-full items-center gap-3 px-4 py-3 text-left ${
          expandable ? "cursor-pointer hover:bg-muted/30" : "cursor-default"
        }`}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground">{name}</p>
          <p className="text-xs text-muted-foreground truncate">{description}</p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {status === "pending" && (
            <Badge variant="secondary" className="gap-1 text-xs">
              <Circle className="h-2.5 w-2.5" />
              Pending
            </Badge>
          )}
          {status === "running" && (
            <Badge className="gap-1.5 text-xs bg-primary/15 text-primary border-primary/30">
              <Spinner />
              Analysing
            </Badge>
          )}
          {status === "done" && (
            <Badge className="gap-1 text-xs bg-emerald-500/15 text-emerald-400 border-emerald-500/30">
              <CheckCircle2 className="h-3 w-3" />
              Done
            </Badge>
          )}
          {expandable && (
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform ${
                open ? "rotate-180" : ""
              }`}
            />
          )}
        </div>
      </button>

      {expandable && open && (
        <div className="border-t border-border/50 px-4 py-3">{children}</div>
      )}
    </div>
  );
}
