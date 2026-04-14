"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ContentBriefDialog } from "@/components/discover/content-brief-dialog";

interface ContentBriefButtonProps {
  /**
   * The DB video ID (NOT the platform_video_id). Used for the API call.
   * Only available when the video has been persisted (tracked or discovered).
   * If null, the button is hidden (can't generate a brief for a search-only result).
   */
  videoId: string | null;
  videoTitle: string;
  isOutlier: boolean;
}

/**
 * "Generate idea" button — only renders for outlier videos that have a DB ID.
 * Opens the ContentBriefDialog which auto-fetches the AI brief on mount.
 */
export function ContentBriefButton({
  videoId,
  videoTitle,
  isOutlier,
}: ContentBriefButtonProps) {
  const [open, setOpen] = useState(false);

  // Only show for outliers with a known DB ID
  if (!isOutlier || !videoId) return null;

  return (
    <>
      <Button
        variant="accent"
        size="sm"
        className="mt-2 w-full gap-1 text-xs"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
      >
        <Sparkles className="h-3 w-3" />
        Generate idea
      </Button>

      <ContentBriefDialog
        videoId={videoId}
        videoTitle={videoTitle}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}
