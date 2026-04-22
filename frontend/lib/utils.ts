import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Combines clsx + tailwind-merge for conflict-free className composition. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a number with thousands separators (e.g., 1234567 → "1,234,567"). */
export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

/** Format a number compactly (e.g., 1234567 → "1.2M"). */
export function formatCompact(n: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n);
}

/** Format a percentage (e.g., 0.045 → "4.5%"). */
export function formatPercent(n: number, fractionDigits = 1): string {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: fractionDigits,
  }).format(n);
}
