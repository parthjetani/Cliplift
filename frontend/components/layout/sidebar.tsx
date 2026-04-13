"use client";

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
} from "lucide-react";

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

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r bg-card md:flex">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <Sparkles className="h-5 w-5 text-primary" />
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

      {/* Plan badge at bottom */}
      <div className="border-t p-3">
        <div className="rounded-md border bg-muted/50 p-3 text-center">
          <p className="text-xs font-medium text-muted-foreground">Free plan</p>
          <Link
            href="/dashboard/settings/billing"
            className="mt-1 inline-block text-xs font-semibold text-primary hover:underline"
          >
            Upgrade →
          </Link>
        </div>
      </div>
    </aside>
  );
}
