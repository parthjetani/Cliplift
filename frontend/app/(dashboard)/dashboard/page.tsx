"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users,
  Video,
  Hash,
  TrendingUp,
  Search,
  Calendar,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/shared/stat-card";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { apiAuth, ApiError } from "@/lib/api";
import { formatCompact } from "@/lib/utils";
import type {
  OverviewResponse,
  RecentOutlier,
  RecentOutliersResponse,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Onboarding (zero-state)
// ---------------------------------------------------------------------------

const onboardingSteps = [
  {
    icon: Search,
    title: "Search trending content",
    description:
      "Find outlier videos across YouTube, Instagram, LinkedIn, and TikTok in seconds.",
    href: "/dashboard/discover",
    cta: "Open search",
  },
  {
    icon: Hash,
    title: "Create your first niche",
    description:
      "Save keywords to track. We'll auto-discover new outliers and notify you.",
    href: "/dashboard/niches/new",
    cta: "Create niche",
  },
  {
    icon: Users,
    title: "Track creators",
    description:
      "Follow up to 3 creators on the free plan. Daily snapshots, growth charts.",
    href: "/dashboard/creators",
    cta: "Browse creators",
  },
  {
    icon: Calendar,
    title: "Schedule your first post",
    description:
      "Connect a YouTube or Instagram account and schedule a Short from Cliplift.",
    href: "/dashboard/settings/connections",
    cta: "Connect account",
  },
];

function OnboardingView() {
  return (
    <>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">
          Welcome to Cliplift
        </h1>
        <p className="mt-2 text-muted-foreground">
          Your workspace is ready. Start by searching for trending content or
          creating your first niche.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {onboardingSteps.map((step) => {
          const Icon = step.icon;
          return (
            <Card key={step.href} className="transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <CardTitle className="text-lg">{step.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="mb-4 text-sm text-muted-foreground">
                  {step.description}
                </p>
                <Link href={step.href}>
                  <Button variant="outline" size="sm">
                    {step.cta} →
                  </Button>
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Analytics dashboard (active-state)
// ---------------------------------------------------------------------------

function AnalyticsDashboard({
  overview,
  outliers,
}: {
  overview: OverviewResponse;
  outliers: RecentOutlier[];
}) {
  return (
    <>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-2 text-muted-foreground">
          Your short-form analytics at a glance.
        </p>
      </div>

      {/* Stat cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Tracked Creators"
          value={overview.tracked_creators}
          icon={Users}
        />
        <StatCard
          label="Tracked Videos"
          value={overview.tracked_videos}
          icon={Video}
        />
        <StatCard
          label="Active Niches"
          value={overview.active_niches}
          icon={Hash}
        />
        <StatCard
          label="Outliers Detected"
          value={overview.total_outliers}
          icon={TrendingUp}
          trend={overview.total_outliers > 0 ? "up" : "neutral"}
          trendLabel={
            overview.total_outliers > 0
              ? `${overview.total_outliers} across all niches`
              : "No outliers yet"
          }
        />
      </div>

      {/* Worker health */}
      {overview.recent_snapshots_24h > 0 && (
        <div className="mb-8 rounded-md border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
          Workers healthy — {overview.recent_snapshots_24h} snapshot
          {overview.recent_snapshots_24h !== 1 ? "s" : ""} collected in the last
          24 hours.
        </div>
      )}

      {/* Recent outliers */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Recent outliers</h2>
        <Link href="/dashboard/discover">
          <Button variant="outline" size="sm">
            <Search className="h-4 w-4" />
            Discover more
          </Button>
        </Link>
      </div>

      {outliers.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center py-12 text-center">
            <TrendingUp className="mb-3 h-8 w-8 text-muted-foreground/50" />
            <p className="text-sm font-medium text-muted-foreground">
              No outliers detected yet
            </p>
            <p className="mt-1 max-w-sm text-xs text-muted-foreground/70">
              Create a niche and run the discovery worker to find viral content.
            </p>
            <Link href="/dashboard/niches/new" className="mt-4">
              <Button size="sm" variant="outline">
                Create niche
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {outliers.map((outlier) => (
            <Card
              key={outlier.niche_video_id}
              className="transition-shadow hover:shadow-sm"
            >
              <CardContent className="flex items-center gap-4 p-4">
                {/* Thumbnail */}
                <div className="h-16 w-16 shrink-0 overflow-hidden rounded bg-muted">
                  {outlier.thumbnail_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={outlier.thumbnail_url}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center">
                      <TrendingUp className="h-5 w-5 text-muted-foreground" />
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-semibold">
                      {outlier.title || "(untitled)"}
                    </p>
                    <PlatformBadge
                      platform={outlier.platform}
                      className="text-[10px]"
                    />
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                    <span>{formatCompact(outlier.views)} views</span>
                    <span>·</span>
                    <span className="font-medium text-green-600">
                      {outlier.outlier_score.toFixed(1)}σ outlier
                    </span>
                    <span>·</span>
                    <span>in &ldquo;{outlier.niche_name}&rdquo;</span>
                  </div>
                </div>

                {/* Badge */}
                <Badge variant="success" className="shrink-0">
                  <TrendingUp className="mr-1 h-3 w-3" />
                  {outlier.outlier_score.toFixed(1)}σ
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Quick links */}
      <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Link href="/dashboard/discover">
          <Card className="transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-3 p-4">
              <Search className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">Search trends</span>
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard/creators">
          <Card className="transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-3 p-4">
              <Users className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">Manage creators</span>
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard/niches">
          <Card className="transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-3 p-4">
              <Hash className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">Manage niches</span>
            </CardContent>
          </Card>
        </Link>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main page — conditional render
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [outliers, setOutliers] = useState<RecentOutlier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [overviewData, outliersData] = await Promise.all([
          apiAuth<OverviewResponse>("/api/v1/analytics/overview"),
          apiAuth<RecentOutliersResponse>(
            "/api/v1/analytics/recent-outliers?limit=10"
          ),
        ]);
        setOverview(overviewData);
        setOutliers(outliersData.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="container max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
        <Skeleton className="mb-4 h-10 w-64" />
        <Skeleton className="mb-8 h-5 w-96" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      </div>
    );
  }

  const hasData =
    overview &&
    (overview.tracked_creators > 0 || overview.active_niches > 0);

  return (
    <div className="container max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
      {hasData && overview ? (
        <AnalyticsDashboard overview={overview} outliers={outliers} />
      ) : (
        <OnboardingView />
      )}
    </div>
  );
}
