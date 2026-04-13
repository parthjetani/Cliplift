import { BarChart3 } from "lucide-react";

interface ChartEmptyProps {
  message?: string;
  hint?: string;
  height?: number;
}

export function ChartEmpty({
  message = "No data yet",
  hint = "Data will appear here once the daily worker has run.",
  height = 300,
}: ChartEmptyProps) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-md border border-dashed text-center"
      style={{ height }}
    >
      <BarChart3 className="mb-3 h-8 w-8 text-muted-foreground/50" />
      <p className="text-sm font-medium text-muted-foreground">{message}</p>
      {hint && (
        <p className="mt-1 max-w-xs text-xs text-muted-foreground/70">
          {hint}
        </p>
      )}
    </div>
  );
}
