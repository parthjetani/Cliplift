"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Calendar as CalendarIcon, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { ContentCalendar } from "@/components/publishing/content-calendar";
import { apiAuth, ApiError } from "@/lib/api";
import type {
  PaginatedResponse,
  ScheduledPostResponse,
} from "@/lib/types";

export default function CalendarPage() {
  const [posts, setPosts] = useState<ScheduledPostResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Backend pagination caps at 100 per page (PaginationParams le=100).
        // The calendar pages through results in case there are more than that
        // — usually unnecessary for a month view but cheap to be correct.
        const allPosts: ScheduledPostResponse[] = [];
        let cursor: string | null = null;
        for (let page = 0; page < 5; page++) {
          const path: string =
            "/api/v1/publishing/scheduled-posts?limit=100" +
            (cursor ? `&cursor=${encodeURIComponent(cursor)}` : "");
          const data = await apiAuth<PaginatedResponse<ScheduledPostResponse>>(
            path
          );
          allPosts.push(...data.items);
          if (!data.has_more || !data.next_cursor) break;
          cursor = data.next_cursor;
        }
        if (cancelled) return;
        // Filter out drafts — they don't belong on a calendar
        setPosts(allPosts.filter((p) => p.status !== "draft"));
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "Failed to load calendar");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="container max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader
          title="Calendar"
          description="Scheduled and published posts on a month grid."
        />
        <Link href="/dashboard/posts/new">
          <Button>
            <Plus className="h-4 w-4" />
            New post
          </Button>
        </Link>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!error && posts === null && <Skeleton className="h-[600px] w-full" />}

      {!error && posts !== null && posts.length === 0 && (
        <EmptyState
          icon={CalendarIcon}
          title="Nothing scheduled yet"
          description="Create your first post and it will appear here."
          action={
            <Link href="/dashboard/posts/new">
              <Button>
                <Plus className="h-4 w-4" />
                New post
              </Button>
            </Link>
          }
        />
      )}

      {!error && posts !== null && posts.length > 0 && (
        <ContentCalendar posts={posts} />
      )}
    </div>
  );
}
