import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { POST_STATUS_LABELS, type PostStatus } from "@/lib/types";

interface PostStatusBadgeProps {
  status: PostStatus;
  className?: string;
}

const statusStyles: Record<PostStatus, string> = {
  draft: "bg-slate-100 text-slate-700 hover:bg-slate-100 border-slate-300",
  scheduled: "bg-blue-100 text-blue-800 hover:bg-blue-100 border-blue-300",
  publishing:
    "bg-amber-100 text-amber-800 hover:bg-amber-100 border-amber-300 animate-pulse",
  published:
    "bg-green-100 text-green-800 hover:bg-green-100 border-green-300",
  failed: "bg-red-100 text-red-800 hover:bg-red-100 border-red-300",
};

/**
 * Color-coded status badge for ScheduledPost rows.
 * `publishing` pulses to signal an in-flight worker run.
 */
export function PostStatusBadge({ status, className }: PostStatusBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn("font-medium", statusStyles[status], className)}
    >
      {POST_STATUS_LABELS[status]}
    </Badge>
  );
}
