import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { POST_STATUS_LABELS, type PostStatus } from "@/lib/types";

interface PostStatusBadgeProps {
  status: PostStatus;
  className?: string;
}

const statusStyles: Record<PostStatus, string> = {
  draft:
    "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-600",
  scheduled:
    "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/50 dark:text-blue-300 dark:border-blue-700",
  publishing:
    "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/50 dark:text-amber-300 dark:border-amber-700 animate-pulse",
  published:
    "bg-brand-teal-100 text-brand-teal-800 border-brand-teal-300 dark:bg-brand-teal-900/50 dark:text-brand-teal-300 dark:border-brand-teal-700",
  failed:
    "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/50 dark:text-red-300 dark:border-red-700",
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
