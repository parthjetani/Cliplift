import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { PLATFORM_LABELS, type Platform } from "@/lib/types";

const platformColors: Record<Platform, string> = {
  youtube: "bg-red-500",
  instagram: "bg-pink-500",
  linkedin: "bg-blue-600",
  tiktok: "bg-black",
};

interface PlatformBadgeProps {
  platform: Platform;
  className?: string;
}

export function PlatformBadge({ platform, className }: PlatformBadgeProps) {
  return (
    <Badge
      className={cn(
        "border-0 text-white",
        platformColors[platform],
        className
      )}
    >
      {PLATFORM_LABELS[platform]}
    </Badge>
  );
}
