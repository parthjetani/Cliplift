"use client";

import { useEffect, useState } from "react";

import { TrialBanner } from "@/components/billing/trial-banner";
import { apiAuth } from "@/lib/api";
import type { TeamResponse } from "@/lib/types";

/**
 * Client-side wrapper that fetches the team once and conditionally renders
 * the trial banner. Mounted in the dashboard layout (server component) between
 * the Header and the main content area.
 */
export function TrialBannerWrapper() {
  const [team, setTeam] = useState<TeamResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiAuth<TeamResponse>("/api/v1/teams/me")
      .then((t) => {
        if (!cancelled) setTeam(t);
      })
      .catch(() => {
        // Silently ignore — banner is non-critical
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!team) return null;

  // Only show banner if trial is active and ending soon, or expired
  if (!team.trial_ends_at && !team.is_trial_expired) return null;
  if (team.plan === "cancelled") return null; // cancelled state has its own UI

  return (
    <TrialBanner
      trialEndsAt={team.trial_ends_at || ""}
      isTrialExpired={team.is_trial_expired}
    />
  );
}
