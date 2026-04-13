"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { DateRangePicker } from "@/components/shared/date-range-picker";
import { LineChart } from "@/components/charts/line-chart";
import { ChartEmpty } from "@/components/charts/chart-empty";
import { ChartSkeleton } from "@/components/charts/chart-skeleton";
import { apiAuth, ApiError } from "@/lib/api";
import { formatCompact, formatPercent } from "@/lib/utils";
import type { CreatorDetail, CreatorTimelineResponse } from "@/lib/types";

export default function CreatorDetailPage() {
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<CreatorDetail | null>(null);
  const [timeline, setTimeline] = useState<CreatorTimelineResponse | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load creator detail
  useEffect(() => {
    const load = async () => {
      try {
        const result = await apiAuth<CreatorDetail>(
          `/api/v1/creators/${params.id}`
        );
        setData(result);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Failed to load creator"
        );
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [params.id]);

  // Load timeline (separate call, re-runs on days change)
  useEffect(() => {
    const loadTimeline = async () => {
      setChartLoading(true);
      try {
        const tl = await apiAuth<CreatorTimelineResponse>(
          `/api/v1/analytics/creators/${params.id}/timeline?days=${days}`
        );
        setTimeline(tl);
      } catch {
        // Timeline is optional — don't block the page
        setTimeline(null);
      } finally {
        setChartLoading(false);
      }
    };
    loadTimeline();
  }, [params.id, days]);

  if (loading) {
    return (
      <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        <Skeleton className="mb-6 h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
        <Link href="/dashboard/creators">
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="h-4 w-4" />
            Back to creators
          </Button>
        </Link>
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error || "Creator not found"}
        </div>
      </div>
    );
  }

  const { creator, tracking, recent_snapshots } = data;
  const latest = recent_snapshots[0];
  const hasTimeline = timeline && timeline.points.length >= 2;

  const formatDate = (d: string) => {
    const date = new Date(d);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  return (
    <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/creators">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back to creators
        </Button>
      </Link>

      {/* Header card */}
      <Card className="mb-6">
        <CardContent className="flex items-start gap-6 p-6">
          <div className="h-20 w-20 shrink-0 overflow-hidden rounded-full bg-muted">
            {creator.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={creator.avatar_url}
                alt={creator.display_name || ""}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center">
                <Users className="h-8 w-8 text-muted-foreground" />
              </div>
            )}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">
                {creator.display_name || creator.username}
              </h1>
              <PlatformBadge platform={creator.platform} />
            </div>
            {creator.username && (
              <p className="mt-1 text-sm text-muted-foreground">
                @{creator.username}
              </p>
            )}
            {creator.bio && <p className="mt-2 text-sm">{creator.bio}</p>}
            {tracking && (
              <p className="mt-3 text-xs text-muted-foreground">
                Tracked since{" "}
                {new Date(tracking.tracked_at).toLocaleDateString()}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Latest snapshot stats */}
      {latest && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">
              Latest snapshot —{" "}
              {new Date(latest.snapshot_date).toLocaleDateString()}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {latest.followers !== null && (
                <Stat
                  label="Followers"
                  value={formatCompact(latest.followers)}
                />
              )}
              {latest.total_videos !== null && (
                <Stat
                  label="Videos"
                  value={formatCompact(latest.total_videos)}
                />
              )}
              {latest.avg_views_30d !== null && (
                <Stat
                  label="Avg views (30d)"
                  value={formatCompact(latest.avg_views_30d)}
                />
              )}
              {latest.avg_engagement_30d !== null && (
                <Stat
                  label="Engagement (30d)"
                  value={formatPercent(latest.avg_engagement_30d)}
                />
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Follower growth chart */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Follower growth</CardTitle>
            <DateRangePicker value={days} onChange={setDays} />
          </div>
        </CardHeader>
        <CardContent>
          {chartLoading ? (
            <ChartSkeleton height={280} />
          ) : hasTimeline ? (
            <LineChart
              data={timeline.points.filter((p) => p.followers !== null)}
              xKey="snapshot_date"
              yKey="followers"
              color="hsl(222.2 47.4% 11.2%)"
              height={280}
              formatX={formatDate}
              yLabel="Followers"
            />
          ) : (
            <ChartEmpty
              message="Not enough data for a chart"
              hint="The daily worker will collect follower data over time. Check back in a few days."
              height={280}
            />
          )}
        </CardContent>
      </Card>

      {/* Avg views chart */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Average views (30d rolling)</CardTitle>
        </CardHeader>
        <CardContent>
          {chartLoading ? (
            <ChartSkeleton height={250} />
          ) : hasTimeline ? (
            <LineChart
              data={timeline.points.filter((p) => p.avg_views_30d !== null)}
              xKey="snapshot_date"
              yKey="avg_views_30d"
              color="#2563eb"
              height={250}
              formatX={formatDate}
              yLabel="Avg views"
            />
          ) : (
            <ChartEmpty height={250} />
          )}
        </CardContent>
      </Card>

      {/* Snapshot history table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Snapshot history</CardTitle>
        </CardHeader>
        <CardContent>
          {recent_snapshots.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No snapshots yet. The daily worker will populate these within 24
              hours.
            </p>
          ) : (
            <div className="space-y-2">
              {recent_snapshots.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded border p-3 text-sm"
                >
                  <span className="font-mono text-xs text-muted-foreground">
                    {new Date(s.snapshot_date).toLocaleDateString()}
                  </span>
                  <div className="flex gap-4 text-xs">
                    {s.followers !== null && (
                      <span>{formatCompact(s.followers)} followers</span>
                    )}
                    {s.total_videos !== null && (
                      <span>{s.total_videos} videos</span>
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}
