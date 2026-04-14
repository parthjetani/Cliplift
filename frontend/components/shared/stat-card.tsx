import type { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Sparkline } from "@/components/charts/sparkline";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendLabel?: string;
  sparklineData?: number[];
  className?: string;
}

export function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  trendLabel,
  sparklineData,
  className,
}: StatCardProps) {
  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold">{value}</p>
            {trend && trendLabel && (
              <div
                className={cn(
                  "flex items-center gap-1 text-xs font-medium",
                  trend === "up" && "text-brand-teal-600",
                  trend === "down" && "text-red-600",
                  trend === "neutral" && "text-muted-foreground"
                )}
              >
                {trend === "up" && <TrendingUp className="h-3 w-3" />}
                {trend === "down" && <TrendingDown className="h-3 w-3" />}
                {trend === "neutral" && <Minus className="h-3 w-3" />}
                {trendLabel}
              </div>
            )}
          </div>

          <div className="flex flex-col items-end gap-2">
            {Icon && (
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10">
                <Icon className="h-4 w-4 text-primary" />
              </div>
            )}
            {sparklineData && sparklineData.length >= 2 && (
              <Sparkline data={sparklineData} height={32} width={80} />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
