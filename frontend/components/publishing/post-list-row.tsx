import Link from "next/link";
import { Calendar, FileVideo } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { PostStatusBadge } from "@/components/publishing/post-status-badge";
import type { ScheduledPostResponse } from "@/lib/types";

interface PostListRowProps {
  post: ScheduledPostResponse;
}

/**
 * Single row in the `/dashboard/posts` list. Click anywhere to navigate to
 * the detail page. Layout is responsive: thumbnail/icon left, metadata
 * center, status + scheduled time right.
 */
export function PostListRow({ post }: PostListRowProps) {
  const scheduledFor = new Date(post.scheduled_for);
  const publishedAt = post.published_at ? new Date(post.published_at) : null;

  return (
    <Link href={`/dashboard/posts/${post.id}`} className="block">
      <Card className="transition-colors hover:bg-muted/50">
        <CardContent className="flex items-center gap-4 p-4">
          {/* Icon */}
          <div className="hidden h-12 w-12 shrink-0 items-center justify-center rounded-md bg-muted sm:flex">
            <FileVideo className="h-5 w-5 text-muted-foreground" />
          </div>

          {/* Title + meta */}
          <div className="min-w-0 flex-1">
            <p className="line-clamp-1 text-sm font-semibold">
              {post.title || "(untitled)"}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <PlatformBadge platform={post.platform} />
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {publishedAt
                  ? `Published ${publishedAt.toLocaleDateString()}`
                  : `Scheduled ${scheduledFor.toLocaleString()}`}
              </span>
              {post.error_message && (
                <span className="line-clamp-1 text-destructive">
                  {post.error_message}
                </span>
              )}
            </div>
          </div>

          {/* Status */}
          <div className="shrink-0">
            <PostStatusBadge status={post.status} />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
