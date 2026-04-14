"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { ArrowLeft, CreditCard, ExternalLink, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { PlanCard } from "@/components/billing/plan-card";
import { UsageMeter } from "@/components/billing/usage-meter";
import { apiAuth, ApiError } from "@/lib/api";
import type {
  BillingPortalResponse,
  OverviewResponse,
  TeamResponse,
  PlatformConnection,
} from "@/lib/types";

const PLANS = [
  {
    key: "creator" as const,
    name: "Creator",
    monthlyPrice: 29,
    features: [
      "Unlimited trend searches",
      "3 tracked creators",
      "1 platform connection",
      "AI content briefs (10/hr)",
    ],
  },
  {
    key: "team" as const,
    name: "Team",
    monthlyPrice: 79,
    highlighted: true,
    features: [
      "Everything in Creator",
      "25 tracked creators",
      "All 4 platforms",
      "Post scheduling & calendar",
      "5 team members",
      "AI briefs (50/hr)",
    ],
  },
  {
    key: "agency" as const,
    name: "Agency",
    monthlyPrice: 149,
    features: [
      "Everything in Team",
      "50 tracked creators",
      "25 team members",
      "API access",
      "Unlimited AI briefs",
      "White-label reports",
    ],
  },
];

export default function BillingPage() {
  const [team, setTeam] = useState<TeamResponse | null>(null);
  const [creatorCount, setCreatorCount] = useState<number | null>(null);
  const [connectionCount, setConnectionCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [portalPending, startPortal] = useTransition();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [t, overview, connections] = await Promise.all([
          apiAuth<TeamResponse>("/api/v1/teams/me"),
          apiAuth<OverviewResponse>("/api/v1/analytics/overview"),
          apiAuth<PlatformConnection[]>("/api/v1/connections"),
        ]);
        if (cancelled) return;
        setTeam(t);
        setCreatorCount(overview.tracked_creators);
        setConnectionCount(new Set(connections.map((c) => c.platform)).size);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "Failed to load billing");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePortal = () => {
    startPortal(async () => {
      try {
        const resp = await apiAuth<BillingPortalResponse>(
          "/api/v1/billing/portal",
          { method: "POST" }
        );
        window.location.href = resp.portal_url;
      } catch (e) {
        setError(
          e instanceof ApiError ? e.message : "Failed to open billing portal"
        );
      }
    });
  };

  // Plan-tier limits for usage meters
  const planLimits: Record<string, { creators: number; platforms: number }> = {
    creator: { creators: 3, platforms: 1 },
    team: { creators: 25, platforms: 4 },
    agency: { creators: 50, platforms: 4 },
    cancelled: { creators: 0, platforms: 0 },
  };

  const limits = team ? planLimits[team.plan] || planLimits.creator : null;

  return (
    <div className="container max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/settings">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back to settings
        </Button>
      </Link>

      <PageHeader
        title="Billing & Plan"
        description="Manage your subscription, view usage, and upgrade."
      />

      {error && (
        <div className="mb-6 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!team ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <>
          {/* Current plan card */}
          <Card className="mb-6">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <CreditCard className="h-4 w-4" />
                Current plan
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <Badge
                  variant={team.plan === "cancelled" ? "destructive" : "default"}
                  className="text-sm"
                >
                  {team.plan === "cancelled"
                    ? "Cancelled"
                    : `${team.plan.charAt(0).toUpperCase()}${team.plan.slice(1)}`}
                </Badge>
                {team.is_trial_active && (
                  <Badge variant="secondary">Trial active</Badge>
                )}
                {team.is_trial_expired && (
                  <Badge variant="destructive">Trial expired</Badge>
                )}
              </div>

              {/* Usage meters */}
              {limits && limits.creators > 0 && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <UsageMeter
                    label="Tracked creators"
                    current={creatorCount ?? 0}
                    limit={limits.creators}
                  />
                  <UsageMeter
                    label="Platform connections"
                    current={connectionCount ?? 0}
                    limit={limits.platforms}
                  />
                </div>
              )}

              {/* Portal button — only for paying customers */}
              {team.stripe_customer_id && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePortal}
                  disabled={portalPending}
                >
                  {portalPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Opening...
                    </>
                  ) : (
                    <>
                      <ExternalLink className="h-4 w-4" />
                      Manage subscription
                    </>
                  )}
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Plan comparison */}
          <h2 className="mb-4 text-lg font-semibold">Choose your plan</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {PLANS.map((p) => (
              <PlanCard
                key={p.key}
                name={p.name}
                monthlyPrice={p.monthlyPrice}
                features={p.features}
                planKey={p.key}
                isCurrent={team.plan === p.key}
                highlighted={p.highlighted}
              />
            ))}
          </div>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            All plans include unlimited trend searches. Annual billing saves 30%.
            No credits, ever.
          </p>
        </>
      )}
    </div>
  );
}
