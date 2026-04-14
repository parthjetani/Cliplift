"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun, Monitor } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Polished 3-state theme toggle: Light → Dark → System → Light...
 *
 * Shows the current active icon with a smooth rotation transition.
 * On hover, a subtle glow matches the current theme accent.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch — render nothing until client-side
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <Button variant="ghost" size="icon" className={cn("h-9 w-9", className)}>
        <span className="h-4 w-4" />
      </Button>
    );
  }

  const cycle = () => {
    if (theme === "light") setTheme("dark");
    else if (theme === "dark") setTheme("system");
    else setTheme("light");
  };

  const label =
    theme === "light"
      ? "Switch to dark mode"
      : theme === "dark"
        ? "Switch to system theme"
        : "Switch to light mode";

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={cycle}
      aria-label={label}
      title={label}
      className={cn(
        "relative h-9 w-9 overflow-hidden transition-colors",
        className
      )}
    >
      {/* Sun — visible in light mode */}
      <Sun
        className={cn(
          "absolute h-4 w-4 transition-all duration-300",
          theme === "light"
            ? "rotate-0 scale-100 opacity-100"
            : "-rotate-90 scale-0 opacity-0"
        )}
      />
      {/* Moon — visible in dark mode */}
      <Moon
        className={cn(
          "absolute h-4 w-4 transition-all duration-300",
          theme === "dark"
            ? "rotate-0 scale-100 opacity-100"
            : "rotate-90 scale-0 opacity-0"
        )}
      />
      {/* Monitor — visible in system mode */}
      <Monitor
        className={cn(
          "absolute h-4 w-4 transition-all duration-300",
          theme === "system"
            ? "rotate-0 scale-100 opacity-100"
            : "rotate-90 scale-0 opacity-0"
        )}
      />
    </Button>
  );
}
