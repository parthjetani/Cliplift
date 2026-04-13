"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { PostComposer } from "@/components/publishing/post-composer";
import { apiAuth, ApiError } from "@/lib/api";
import type {
  PlatformConnection,
  Video,
  VideoDetail,
} from "@/lib/types";

export default function NewPostPage() {
  const searchParams = useSearchParams();
  const inspiredById = searchParams.get("inspired_by");

  const [connections, setConnections] = useState<PlatformConnection[] | null>(
    null
  );
  const [inspiredBy, setInspiredBy] = useState<Video | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Fetch connections + (optionally) the inspired_by video in parallel
        const [conns, vid] = await Promise.all([
          apiAuth<PlatformConnection[]>("/api/v1/connections"),
          inspiredById
            ? apiAuth<VideoDetail>(`/api/v1/videos/${inspiredById}`).catch(
                () => null
              )
            : Promise.resolve(null),
        ]);
        if (cancelled) return;
        setConnections(conns);
        setInspiredBy(vid?.video ?? null);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof ApiError ? e.message : "Failed to load composer"
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [inspiredById]);

  return (
    <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/discover">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
      </Link>

      <PageHeader
        title="Schedule a post"
        description="Upload a video and pick when it should publish. The publish worker checks every 5 minutes."
      />

      {error ? (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      ) : connections === null ? (
        <div className="grid gap-6 md:grid-cols-2">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : (
        <PostComposer connections={connections} inspiredBy={inspiredBy} />
      )}
    </div>
  );
}
