"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { apiAuth, ApiError } from "@/lib/api";
import type { TeamResponse } from "@/lib/types";

export default function TeamSettingsPage() {
  const [team, setTeam] = useState<TeamResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const t = await apiAuth<TeamResponse>("/api/v1/teams/me");
        if (!cancelled) setTeam(t);
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Failed to load");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const maxUsers =
    team?.plan === "agency" ? 25 : team?.plan === "team" ? 5 : 1;
  const canInvite = maxUsers > 1;

  return (
    <div className="container max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/settings">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back to settings
        </Button>
      </Link>

      <PageHeader
        title="Team Members"
        description="Manage who has access to your workspace."
      />

      {error && (
        <div className="mb-6 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!team ? (
        <Skeleton className="h-48 w-full" />
      ) : canInvite ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4" />
              Members ({maxUsers} seats)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4 text-sm text-muted-foreground">
              Team member invites are coming soon. You have {maxUsers} seat
              {maxUsers > 1 ? "s" : ""} available on your {team.plan} plan.
            </p>
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          icon={Users}
          title="Single-user plan"
          description="The Creator plan includes 1 seat. Upgrade to Team ($79/mo) to invite up to 5 members."
          action={
            <Link href="/dashboard/settings/billing">
              <Button>Upgrade to invite members</Button>
            </Link>
          }
        />
      )}
    </div>
  );
}
