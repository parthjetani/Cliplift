"use client";

import Link from "next/link";
import { Clock } from "lucide-react";

import { Button } from "@/components/ui/button";

interface TrialBannerProps {
  trialEndsAt: string;
  isTrialExpired: boolean;
}

/**
 * Top-of-dashboard banner shown when the user's trial is ending soon
 * (< 4 days remaining) or has already expired.
 */
export function TrialBanner({ trialEndsAt, isTrialExpired }: TrialBannerProps) {
  if (isTrialExpired) {
    return (
      <div className="border-b border-red-200 bg-red-50 px-4 py-2.5">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-red-800">
            <Clock className="h-4 w-4" />
            <span>
              Your trial has ended. Pick a plan to continue tracking and
              publishing.
            </span>
          </div>
          <Link href="/dashboard/settings/billing">
            <Button size="sm" variant="destructive">
              Choose a plan
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const daysLeft = Math.max(
    0,
    Math.ceil(
      (new Date(trialEndsAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
    )
  );

  if (daysLeft > 3) return null;

  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-2.5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-amber-800">
          <Clock className="h-4 w-4" />
          <span>
            {daysLeft === 0
              ? "Your trial ends today."
              : `Your trial ends in ${daysLeft} day${daysLeft > 1 ? "s" : ""}.`}
            {" "}Upgrade to keep full access.
          </span>
        </div>
        <Link href="/dashboard/settings/billing">
          <Button size="sm">Upgrade now</Button>
        </Link>
      </div>
    </div>
  );
}
