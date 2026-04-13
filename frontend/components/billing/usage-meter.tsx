import { cn } from "@/lib/utils";

interface UsageMeterProps {
  label: string;
  current: number;
  limit: number;
  unit?: string;
}

/**
 * Horizontal bar showing current/limit usage for a billing metric.
 * Turns amber at 80% and red at 100%.
 */
export function UsageMeter({ label, current, limit, unit }: UsageMeterProps) {
  const pct = limit > 0 ? Math.min((current / limit) * 100, 100) : 0;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">
          {current} / {limit}
          {unit && ` ${unit}`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            pct < 80 ? "bg-primary" : pct < 100 ? "bg-amber-500" : "bg-red-500"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
