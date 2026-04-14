"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Users,
  Hash,
  Calendar,
  Send,
  BarChart3,
  Settings,
} from "lucide-react";

import { Logo } from "@/components/brand/logo";

import { apiAuth } from "@/lib/api";
import type { TeamResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/discover", label: "Discover", icon: Search },
  { href: "/dashboard/creators", label: "Creators", icon: Users },
  { href: "/dashboard/niches", label: "Niches", icon: Hash },
  { href: "/dashboard/posts", label: "Posts", icon: Send },
  { href: "/dashboard/calendar", label: "Calendar", icon: Calendar },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [team, setTeam] = useState<TeamResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiAuth<TeamResponse>("/api/v1/teams/me")
      .then((t) => {
        if (!cancelled) setTeam(t);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const planLabel = team
    ? team.plan === "cancelled"
      ? "Cancelled"
      : team.is_trial_active
        ? `${team.plan.charAt(0).toUpperCase()}${team.plan.slice(1)} trial`
        : `${team.plan.charAt(0).toUpperCase()}${team.plan.slice(1)} plan`
    : null;

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r bg-card md:flex">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <Logo variant="icon" size="md" />
        <span className="text-lg font-bold tracking-tight">Cliplift</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Plan badge at bottom */}
      <div className="border-t p-3">
        <div className="rounded-md border bg-muted/50 p-3 text-center">
          <p className="text-xs font-medium text-muted-foreground">
            {planLabel ?? "Loading…"}
          </p>
          {team?.plan !== "agency" && (
            <Link
              href="/dashboard/settings/billing"
              className="mt-1 inline-block text-xs font-semibold text-primary hover:underline"
            >
              {team?.plan === "cancelled" ? "Reactivate →" : "Upgrade →"}
            </Link>
          )}
        </div>
      </div>
    </aside>
  );
}
