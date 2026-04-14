"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import Image from "next/image";

import { cn } from "@/lib/utils";

type LogoVariant = "icon" | "wordmark";
type LogoSize = "sm" | "md" | "lg";

interface LogoProps {
  variant?: LogoVariant;
  size?: LogoSize;
  className?: string;
}

const ICON_SIZES: Record<LogoSize, number> = { sm: 20, md: 24, lg: 32 };
const WORDMARK_WIDTHS: Record<LogoSize, number> = { sm: 90, md: 110, lg: 140 };
const WORDMARK_HEIGHTS: Record<LogoSize, number> = { sm: 20, md: 24, lg: 31 };

const ASSETS = {
  icon: { light: "/logo/icon.svg", dark: "/logo/icon-dark.svg" },
  wordmark: { light: "/logo/wordmark.svg", dark: "/logo/wordmark-dark.svg" },
};

/**
 * Brand logo component — renders the actual Cliplift SVG assets.
 *
 * Props:
 *   variant — "icon" (chart mark only) or "wordmark" (icon + "Cliplift" text)
 *   size — "sm" | "md" | "lg"
 *   className — passthrough for custom Tailwind sizing/spacing overrides
 *
 * Automatically switches between light and dark SVG based on the active theme.
 * Uses a mounted state check to avoid hydration mismatch (standard next-themes pattern).
 */
export function Logo({ variant = "icon", size = "md", className }: LogoProps) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const theme = mounted && resolvedTheme === "dark" ? "dark" : "light";
  const src = ASSETS[variant][theme];

  if (variant === "wordmark") {
    const w = WORDMARK_WIDTHS[size];
    const h = WORDMARK_HEIGHTS[size];
    return (
      <Image
        src={src}
        alt="Cliplift"
        width={w}
        height={h}
        priority
        className={cn("h-auto", className)}
      />
    );
  }

  const s = ICON_SIZES[size];
  return (
    <Image
      src={src}
      alt="Cliplift"
      width={s}
      height={s}
      priority
      className={className}
    />
  );
}
