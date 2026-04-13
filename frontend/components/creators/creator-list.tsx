"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { Users, Trash2, ExternalLink, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { TrackCreatorDialog } from "@/components/creators/track-creator-dialog";
import { apiAuth, ApiError } from "@/lib/api";
import { formatCompact } from "@/lib/utils";
import type { PaginatedResponse, TrackedCreator } from "@/lib/types";

export function CreatorList() {
  const [data, setData] = useState<PaginatedResponse<TrackedCreator> | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [, startTransition] = useTransition();

  const refresh = async () => {
    setLoading(true);
    try {
      const result = await apiAuth<PaginatedResponse<TrackedCreator>>(
        "/api/v1/creators?limit=50"
      );
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load creators");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUntrack = (creatorId: string) => {
    startTransition(async () => {
      try {
        await apiAuth(`/api/v1/creators/${creatorId}/untrack`, {
          method: "DELETE",
        });
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to untrack");
      }
    });
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No tracked creators yet"
        description="Track creators to get daily snapshots of their growth and outlier videos."
        action={<TrackCreatorDialog onSuccess={refresh} />}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data.items.length} creator{data.items.length !== 1 ? "s" : ""} tracked
        </p>
        <TrackCreatorDialog onSuccess={refresh} />
      </div>

      <div className="grid grid-cols-1 gap-3">
        {data.items.map((tc) => (
          <Card key={tc.id} className="transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-4 p-4">
              {/* Avatar */}
              <div className="h-12 w-12 shrink-0 overflow-hidden rounded-full bg-muted">
                {tc.creator.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={tc.creator.avatar_url}
                    alt={tc.creator.display_name || ""}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center">
                    <Users className="h-5 w-5 text-muted-foreground" />
                  </div>
                )}
              </div>

              {/* Name + meta */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Link
                    href={`/dashboard/creators/${tc.creator.id}`}
                    className="truncate font-semibold hover:underline"
                  >
                    {tc.creator.display_name ||
                      tc.creator.username ||
                      tc.creator.platform_id}
                  </Link>
                  <PlatformBadge platform={tc.creator.platform} />
                </div>
                <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                  {tc.creator.username && <span>@{tc.creator.username}</span>}
                  {tc.latest_followers !== null && (
                    <span>{formatCompact(tc.latest_followers)} followers</span>
                  )}
                  <span>
                    Tracked {new Date(tc.tracked_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex shrink-0 items-center gap-2">
                <Link href={`/dashboard/creators/${tc.creator.id}`}>
                  <Button variant="ghost" size="icon">
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </Link>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleUntrack(tc.creator.id)}
                  title="Untrack"
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
