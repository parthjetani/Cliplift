import { TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";

interface OutlierBadgeProps {
  score: number | null;
  isOutlier: boolean;
}

export function OutlierBadge({ score, isOutlier }: OutlierBadgeProps) {
  if (!isOutlier || score === null) {
    return null;
  }

  return (
    <Badge variant="success" className="gap-1">
      <TrendingUp className="h-3 w-3" />
      {score.toFixed(1)}σ outlier
    </Badge>
  );
}
