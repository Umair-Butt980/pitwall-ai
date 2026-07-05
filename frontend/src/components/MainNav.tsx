"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";

const NAV_LINKS = [
  { href: "/", label: "Calendar" },
  { href: "/live", label: "Live" },
  { href: "/standings", label: "Standings" },
  { href: "/history", label: "History" },
];

export default function MainNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-border/50 bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="font-mono text-lg font-bold tracking-widest text-primary">
            PITWALL AI
          </span>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            F1 Race Prediction
          </span>
        </div>

        <nav className="flex items-center gap-1">
          {NAV_LINKS.map(({ href, label }) => (
            <Button
              key={href}
              asChild
              variant={pathname === href ? "secondary" : "ghost"}
              size="sm"
            >
              <Link href={href}>{label}</Link>
            </Button>
          ))}
        </nav>
      </div>
    </header>
  );
}
