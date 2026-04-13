"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { PostListRow } from "@/components/publishing/post-list-row";
import { apiAuth, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  POST_STATUS_LABELS,
  type PaginatedResponse,
  type PostStatus,
  type ScheduledPostResponse,
} from "@/lib/types";

type StatusFilter = "all" | PostStatus;

const FILTERS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "scheduled", label: POST_STATUS_LABELS.scheduled },
  { key: "publishing", label: POST_STATUS_LABELS.publishing },
  { key: "published", label: POST_STATUS_LABELS.published },
  { key: "failed", label: POST_STATUS_LABELS.failed },
  { key: "draft", label: POST_STATUS_LABELS.draft },
];

export default function PostsPage() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [posts, setPosts] = useState<ScheduledPostResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPosts(null);
    setError(null);
    (async () => {
      try {
        const path =
          filter === "all"
            ? "/api/v1/publishing/scheduled-posts?limit=100"
            : `/api/v1/publishing/scheduled-posts?status=${filter}&limit=100`;
        const data = await apiAuth<PaginatedResponse<ScheduledPostResponse>>(
          path
        );
        if (!cancelled) setPosts(data.items);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "Failed to load posts");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [filter]);

  return (
    <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader
          title="Posts"
          description="Drafts, scheduled posts, and published history."
        />
        <Link href="/dashboard/posts/new">
          <Button>
            <Plus className="h-4 w-4" />
            New post
          </Button>
        </Link>
      </div>

      {/* Status filter tabs */}
      <div className="mb-4 flex flex-wrap gap-1 border-b">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              filter === f.key
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Body */}
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!error && posts === null && (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      )}

      {!error && posts !== null && posts.length === 0 && (
        <EmptyState
          icon={Send}
          title={
            filter === "all"
              ? "No posts yet"
              : `No ${POST_STATUS_LABELS[filter as PostStatus].toLowerCase()} posts`
          }
          description="Schedule your first post from the discover feed or click 'New post'."
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
        <div className="space-y-2">
          {posts.map((post) => (
            <PostListRow key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
