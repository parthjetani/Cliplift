"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Play, Heart, MessageCircle, Share2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { DateRangePicker } from "@/components/shared/date-range-picker";
import { LineChart } from "@/components/charts/line-chart";
import { AreaChart } from "@/components/charts/area-chart";
import { ChartEmpty } from "@/components/charts/chart-empty";
import { ChartSkeleton } from "@/components/charts/chart-skeleton";
import { OutlierBadge } from "@/components/discover/outlier-badge";
import { apiAuth, ApiError } from "@/lib/api";
import { formatCompact } from "@/lib/utils";
import type { VideoDetail, VideoTimelineResponse } from "@/lib/types";

const HOUR_OPTIONS = [
  { label: "24h", days: 24 },
  { label: "72h", days: 72 },
  { label: "7d", days: 168 },
];

export default function VideoDetailPage() {
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<VideoDetail | null>(null);
  const [timeline, setTimeline] = useState<VideoTimelineResponse | null>(null);
  const [hours, setHours] = useState(72);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const result = await apiAuth<VideoDetail>(
          `/api/v1/videos/${params.id}`
        );
        setData(result);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Failed to load video"
        );
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [params.id]);

  useEffect(() => {
    const loadTimeline = async () => {
      setChartLoading(true);
      try {
        const tl = await apiAuth<VideoTimelineResponse>(
          `/api/v1/analytics/videos/${params.id}/timeline?hours=${hours}`
        );
        setTimeline(tl);
      } catch {
        setTimeline(null);
      } finally {
        setChartLoading(false);
      }
    };
    loadTimeline();
  }, [params.id, hours]);

  if (loading) {
    return (
      <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        <Skeleton className="mb-6 h-32 w-full" />
        <ChartSkeleton />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        <Link href="/dashboard/discover">
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
        </Link>
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error || "Video not found"}
        </div>
      </div>
    );
  }

  const { video } = data;
  const hasTimeline = timeline && timeline.points.length >= 2;

  const formatTime = (d: string) => {
    const date = new Date(d);
    if (hours <= 24) {
      return `${date.getHours()}:${date.getMinutes().toString().padStart(2, "0")}`;
    }
    return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}h`;
  };

  return (
    <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/discover">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
      </Link>

      {/* Video header */}
      <Card className="mb-6">
        <CardContent className="flex items-start gap-6 p-6">
          {/* Thumbnail */}
          <div className="h-32 w-24 shrink-0 overflow-hidden rounded bg-muted">
            {video.thumbnail_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={video.thumbnail_url}
                alt=""
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center">
                <Play className="h-8 w-8 text-muted-foreground" />
              </div>
            )}
          </div>

          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold">
                {video.title || "(untitled)"}
              </h1>
              <PlatformBadge platform={video.platform} />
              <OutlierBadge
                score={video.outlier_score}
                isOutlier={video.is_outlier}
              />
            </div>

            {video.description && (
              <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                {video.description}
              </p>
            )}

            <div className="mt-3 flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Play className="h-3.5 w-3.5" />
                {formatCompact(video.latest_views)} views
              </span>
              <span className="flex items-center gap-1">
                <Heart className="h-3.5 w-3.5" />
                {formatCompact(video.latest_likes)}
              </span>
              <span className="flex items-center gap-1">
                <MessageCircle className="h-3.5 w-3.5" />
                {formatCompact(video.latest_comments)}
              </span>
              {video.latest_shares > 0 && (
                <span className="flex items-center gap-1">
                  <Share2 className="h-3.5 w-3.5" />
                  {formatCompact(video.latest_shares)}
                </span>
              )}
            </div>

            {video.published_at && (
              <p className="mt-2 text-xs text-muted-foreground">
                Published{" "}
                {new Date(video.published_at).toLocaleDateString()}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Views over time */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Views over time</CardTitle>
            <DateRangePicker
              value={hours}
              onChange={setHours}
              options={HOUR_OPTIONS}
            />
          </div>
        </CardHeader>
        <CardContent>
          {chartLoading ? (
            <ChartSkeleton height={280} />
          ) : hasTimeline ? (
            <LineChart
              data={timeline.points.filter((p) => p.views !== null)}
              xKey="snapshot_at"
              yKey="views"
              color="hsl(222.2 47.4% 11.2%)"
              height={280}
              formatX={formatTime}
              yLabel="Views"
            />
          ) : (
            <ChartEmpty
              message="Not enough data for a chart"
              hint="The video worker snapshots every 6 hours. Check back soon."
              height={280}
            />
          )}
        </CardContent>
      </Card>

      {/* View velocity curve */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">
            View velocity (views/hour)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {chartLoading ? (
            <ChartSkeleton height={250} />
          ) : hasTimeline ? (
            <AreaChart
              data={timeline.points.filter((p) => p.view_velocity !== null)}
              xKey="snapshot_at"
              yKey="view_velocity"
              color="#16a34a"
              height={250}
              formatX={formatTime}
              yLabel="Views/hr"
            />
          ) : (
            <ChartEmpty
              message="Velocity data requires 2+ snapshots"
              hint="Run 'make worker-videos' to collect another snapshot."
              height={250}
            />
          )}
        </CardContent>
      </Card>

      {/* Snapshot history */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Snapshot history</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_snapshots.length === 0 ? (
            <p className="text-sm text-muted-foreground">No snapshots yet.</p>
          ) : (
            <div className="space-y-2">
              {data.recent_snapshots.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded border p-3 text-sm"
                >
                  <span className="font-mono text-xs text-muted-foreground">
                    {new Date(s.snapshot_at).toLocaleString()}
                  </span>
                  <div className="flex gap-4 text-xs">
                    {s.views !== null && (
                      <span>{formatCompact(s.views)} views</span>
                    )}
                    {s.view_velocity !== null && (
                      <span className="text-green-600">
                        {formatCompact(s.view_velocity)} views/hr
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
