"use client";

import { useEffect, useState, useTransition } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Hash, Trash2, RefreshCw, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { ConfirmDelete } from "@/components/shared/confirm-delete";
import { StatCard } from "@/components/shared/stat-card";
import { BarChart } from "@/components/charts/bar-chart";
import { LineChart } from "@/components/charts/line-chart";
import { ChartEmpty } from "@/components/charts/chart-empty";
import { VideoCard } from "@/components/discover/video-card";
import { apiAuth, ApiError } from "@/lib/api";
import { PLATFORM_LABELS } from "@/lib/types";
import type {
  Niche,
  NicheFeedItem,
  NichePerformanceResponse,
  PaginatedResponse,
  VideoSearchResult,
} from "@/lib/types";

export default function NicheDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [niche, setNiche] = useState<Niche | null>(null);
  const [feed, setFeed] = useState<PaginatedResponse<NicheFeedItem> | null>(
    null
  );
  const [perf, setPerf] = useState<NichePerformanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [deletePending, startDeleteTransition] = useTransition();

  const loadAll = async () => {
    setLoading(true);
    try {
      const [n, f, p] = await Promise.all([
        apiAuth<Niche>(`/api/v1/niches/${params.id}`),
        apiAuth<PaginatedResponse<NicheFeedItem>>(
          `/api/v1/niches/${params.id}/feed?limit=24`
        ),
        apiAuth<NichePerformanceResponse>(
          `/api/v1/analytics/niches/${params.id}/performance?days=30`
        ).catch(() => null),
      ]);
      setNiche(n);
      setFeed(f);
      setPerf(p);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  const handleDelete = () => {
    startDeleteTransition(async () => {
      try {
        await apiAuth(`/api/v1/niches/${params.id}`, { method: "DELETE" });
        router.push("/dashboard/niches");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to delete");
      }
    });
  };

  if (loading) {
    return (
      <div className="container max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        <Skeleton className="mb-6 h-32 w-full" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-72 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !niche || !feed) {
    return (
      <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        <Link href="/dashboard/niches">
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="h-4 w-4" />
            Back to niches
          </Button>
        </Link>
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error || "Niche not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="container max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/niches">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back to niches
        </Button>
      </Link>

      {/* Header */}
      <Card className="mb-6">
        <CardContent className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-2xl font-bold">{niche.name}</h1>

              <div className="mt-3 flex flex-wrap gap-1">
                {niche.keywords.map((kw) => (
                  <Badge key={kw} variant="outline" className="text-xs">
                    {kw}
                  </Badge>
                ))}
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {niche.platforms.map((p) => (
                  <PlatformBadge key={p} platform={p} />
                ))}
              </div>

              <p className="mt-3 text-xs text-muted-foreground">
                {niche.last_analyzed_at
                  ? `Last analyzed ${new Date(niche.last_analyzed_at).toLocaleString()}`
                  : "Awaiting first worker run"}
              </p>
            </div>

            <ConfirmDelete
              title={`Delete "${niche.name}"?`}
              description="This will permanently delete the niche and all its discovered videos. The videos themselves stay in your library."
              confirmText="Delete niche"
              onConfirm={handleDelete}
            >
              <Button
                variant="ghost"
                size="icon"
                disabled={deletePending}
                title="Delete niche"
              >
                {deletePending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4 text-destructive" />
                )}
              </Button>
            </ConfirmDelete>
          </div>
        </CardContent>
      </Card>

      {/* Analytics charts */}
      {perf && (perf.platform_breakdown.length > 0 || perf.daily.length > 0) && (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Total Videos"
            value={perf.total_videos}
            icon={Hash}
          />
          <StatCard
            label="Outliers Detected"
            value={perf.total_outliers}
            icon={Hash}
            trend={perf.total_outliers > 0 ? "up" : "neutral"}
            trendLabel={perf.total_outliers > 0 ? "Z-score >= 3.0" : "None yet"}
          />
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                Platform breakdown
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-4">
              {perf.platform_breakdown.length > 0 ? (
                <BarChart
                  data={perf.platform_breakdown.map((pb) => ({
                    name: (PLATFORM_LABELS as Record<string, string>)[pb.platform] || pb.platform,
                    value: pb.count,
                  }))}
                  height={120}
                />
              ) : (
                <ChartEmpty height={120} message="No data" />
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {perf && perf.daily.length >= 2 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Videos discovered per day</CardTitle>
          </CardHeader>
          <CardContent>
            <LineChart
              data={perf.daily}
              xKey="day"
              yKey="videos_discovered"
              color="#6366F1"
              height={200}
              formatX={(d: string) => {
                const date = new Date(d);
                return `${date.getMonth() + 1}/${date.getDate()}`;
              }}
              yLabel="Videos"
            />
          </CardContent>
        </Card>
      )}

      {/* Feed */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Discovered videos</h2>
        <Button variant="outline" size="sm" onClick={loadAll}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {feed.items.length === 0 ? (
        <EmptyState
          icon={Hash}
          title="No videos discovered yet"
          description="The auto-discovery worker runs hourly. In dev, run 'make worker-discover' to trigger it manually."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {feed.items.map((item) => {
            // Adapt the niche feed item's Video to the VideoSearchResult shape
            // expected by VideoCard
            const video: VideoSearchResult = {
              platform: item.video.platform,
              platform_video_id: item.video.platform_video_id,
              url: item.video.thumbnail_url || "#",
              title: item.video.title || "(no title)",
              description: item.video.description,
              creator_username: "",
              creator_display_name: null,
              creator_platform_id: null,
              creator_followers: null,
              views: item.video.latest_views,
              likes: item.video.latest_likes,
              comments: item.video.latest_comments,
              shares: item.video.latest_shares,
              engagement_rate: item.video.latest_engagement_rate,
              published_at: item.video.published_at,
              thumbnail_url: item.video.thumbnail_url,
              duration_seconds: item.video.duration_seconds,
              hashtags: item.video.hashtags || [],
              outlier_score: item.outlier_score,
              is_outlier: (item.outlier_score ?? 0) >= 3.0,
            };
            return <VideoCard key={item.id} video={video} dbVideoId={item.video.id} />;
          })}
        </div>
      )}
    </div>
  );
}
