"use client";

import { cn } from "@/lib/utils";

interface DateRangePickerProps {
  value: number;
  onChange: (days: number) => void;
  options?: { label: string; days: number }[];
}

const DEFAULT_OPTIONS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
];

/**
 * Simple segmented control for date ranges. No calendar — just preset windows.
 * The selected value is in days (or hours for video timelines).
 */
export function DateRangePicker({
  value,
  onChange,
  options = DEFAULT_OPTIONS,
}: DateRangePickerProps) {
  return (
    <div className="inline-flex rounded-md border bg-muted p-0.5 text-xs">
      {options.map((opt) => (
        <button
          key={opt.days}
          type="button"
          onClick={() => onChange(opt.days)}
          className={cn(
            "rounded-sm px-3 py-1 font-medium transition-colors",
            value === opt.days
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
