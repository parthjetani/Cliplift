"use client";

import { useEffect, useState, useTransition } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Calendar,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDelete } from "@/components/shared/confirm-delete";
import { PageHeader } from "@/components/shared/page-header";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { PostStatusBadge } from "@/components/publishing/post-status-badge";
import { apiAuth, ApiError } from "@/lib/api";
import type { ScheduledPostResponse } from "@/lib/types";

export default function PostDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [post, setPost] = useState<ScheduledPostResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletePending, startDeleteTransition] = useTransition();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiAuth<ScheduledPostResponse>(
          `/api/v1/publishing/scheduled-posts/${params.id}`
        );
        if (!cancelled) setPost(data);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "Failed to load post");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  const handleDelete = () => {
    startDeleteTransition(async () => {
      try {
        await apiAuth(`/api/v1/publishing/scheduled-posts/${params.id}`, {
          method: "DELETE",
        });
        router.push("/dashboard/posts");
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Failed to delete");
      }
    });
  };

  if (error) {
    return (
      <div className="container max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        <Link href="/dashboard/posts">
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="h-4 w-4" />
            Back to posts
          </Button>
        </Link>
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      </div>
    );
  }

  if (!post) {
    return (
      <div className="container max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        <Skeleton className="mb-6 h-8 w-32" />
        <Skeleton className="mb-4 h-12 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const scheduledFor = new Date(post.scheduled_for);
  const publishedAt = post.published_at ? new Date(post.published_at) : null;
  const isEditable = ["draft", "scheduled", "failed"].includes(post.status);

  return (
    <div className="container max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/posts">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back to posts
        </Button>
      </Link>

      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader
          title={post.title || "(untitled)"}
          description={`Created ${new Date(post.created_at).toLocaleString()}`}
        />
        <div className="flex items-center gap-2">
          <PostStatusBadge status={post.status} />
          {isEditable && (
            <ConfirmDelete
              title="Delete this post?"
              description="This permanently deletes the scheduled post and its uploaded video file."
              confirmText="Delete post"
              onConfirm={handleDelete}
            >
              <Button
                variant="ghost"
                size="icon"
                disabled={deletePending}
                title="Delete post"
              >
                {deletePending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4 text-destructive" />
                )}
              </Button>
            </ConfirmDelete>
          )}
        </div>
      </div>

      {/* Status banner */}
      {post.status === "published" && (
        <Card className="mb-4 border-brand-teal-500/40 bg-brand-teal-500/5">
          <CardContent className="flex items-start gap-3 p-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-brand-teal-600" />
            <div className="flex-1">
              <p className="text-sm font-medium">
                Published{publishedAt && ` ${publishedAt.toLocaleString()}`}
              </p>
              {post.media_url && (
                <a
                  href={post.media_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  View on {post.platform}
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {post.platform_post_id && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Platform ID: {post.platform_post_id}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {post.status === "failed" && post.error_message && (
        <Card className="mb-4 border-destructive/40 bg-destructive/5">
          <CardContent className="flex items-start gap-3 p-4">
            <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <div className="flex-1">
              <p className="text-sm font-medium">Publishing failed</p>
              <p className="mt-1 break-words text-xs text-muted-foreground">
                {post.error_message}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Metadata */}
      <Card className="mb-4">
        <CardContent className="space-y-4 p-6">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Platform
              </p>
              <div className="mt-1">
                <PlatformBadge platform={post.platform} />
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Scheduled for
              </p>
              <p className="mt-1 flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                {scheduledFor.toLocaleString()}
              </p>
            </div>
          </div>

          {post.description && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Description
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm">
                {post.description}
              </p>
            </div>
          )}

          {post.hashtags && post.hashtags.length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Hashtags
              </p>
              <p className="mt-1 text-sm text-primary">
                {post.hashtags.map((h) => `#${h}`).join(" ")}
              </p>
            </div>
          )}

          {post.file_key && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                File
              </p>
              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                {post.file_key}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {post.inspired_by_video_id && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="flex items-center gap-3 p-4">
            <Sparkles className="h-4 w-4 text-primary" />
            <p className="flex-1 text-sm">
              Inspired by an outlier video.{" "}
              <Link
                href={`/dashboard/videos/${post.inspired_by_video_id}`}
                className="text-primary hover:underline"
              >
                View source
              </Link>
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
