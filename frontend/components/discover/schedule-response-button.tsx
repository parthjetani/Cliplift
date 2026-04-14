"use client";

import Link from "next/link";
import { CalendarPlus } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ScheduleResponseButtonProps {
  /**
   * The DB video ID (NOT the platform_video_id). Used to pre-fill the
   * composer's `inspired_by` query param. Only available for persisted videos
   * (tracked or auto-discovered) — search-only results don't have a DB ID.
   */
  videoId: string | null;
  isOutlier: boolean;
}

/**
 * "Schedule a response" CTA — only renders for outlier videos that have a
 * DB ID. Routes to the post composer with `inspired_by=<video_id>` so the
 * source video appears in the composer header.
 */
export function ScheduleResponseButton({
  videoId,
  isOutlier,
}: ScheduleResponseButtonProps) {
  if (!isOutlier || !videoId) return null;

  return (
    <Link
      href={`/dashboard/posts/new?inspired_by=${videoId}`}
      onClick={(e) => e.stopPropagation()}
      className="block"
    >
      <Button
        variant="outline"
        size="sm"
        className="mt-2 w-full gap-1 text-xs text-accent"
      >
        <CalendarPlus className="h-3 w-3" />
        Schedule a response
      </Button>
    </Link>
  );
}
