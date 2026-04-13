"use client";

import { useState } from "react";
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
  Sparkles,
  Menu,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
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

/**
 * Mobile slide-out navigation sheet. Renders a hamburger button that opens
 * a full-height overlay with the same nav items as the desktop sidebar.
 * Only visible on screens < md (768px).
 */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <div className="md:hidden">
      {/* Hamburger trigger */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(true)}
        aria-label="Open navigation menu"
      >
        <Menu className="h-5 w-5" />
      </Button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Slide-out panel */}
      <div
        className={cn(
          "fixed left-0 top-0 z-50 flex h-full w-72 flex-col bg-card shadow-xl transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex h-16 items-center justify-between border-b px-5">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <span className="text-lg font-bold tracking-tight">Cliplift</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setOpen(false)}
            aria-label="Close navigation menu"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Plan badge */}
        <div className="border-t p-3">
          <div className="rounded-md border bg-muted/50 p-3 text-center">
            <p className="text-xs font-medium text-muted-foreground">
              Free plan
            </p>
            <Link
              href="/dashboard/settings/billing"
              onClick={() => setOpen(false)}
              className="mt-1 inline-block text-xs font-semibold text-primary hover:underline"
            >
              Upgrade →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
