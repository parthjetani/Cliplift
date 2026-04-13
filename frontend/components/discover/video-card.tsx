import Image from "next/image";
import Link from "next/link";
import {
  Heart,
  MessageCircle,
  Play,
  Share2,
  ExternalLink,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { OutlierBadge } from "@/components/discover/outlier-badge";
import { ContentBriefButton } from "@/components/discover/content-brief-button";
import { ScheduleResponseButton } from "@/components/discover/schedule-response-button";
import { cn, formatCompact } from "@/lib/utils";
import { PLATFORM_LABELS, type VideoSearchResult } from "@/lib/types";

interface VideoCardProps {
  video: VideoSearchResult;
  /** DB UUID for persisted videos. When set + outlier, shows "Generate idea" button. */
  dbVideoId?: string;
}

const platformColors: Record<string, string> = {
  youtube: "bg-red-500",
  instagram: "bg-pink-500",
  linkedin: "bg-blue-600",
  tiktok: "bg-black",
};

export function VideoCard({ video, dbVideoId }: VideoCardProps) {
  return (
    <Card
      className={cn(
        "group overflow-hidden transition-all hover:shadow-lg",
        video.is_outlier && "ring-2 ring-green-500/50"
      )}
    >
      {/* Thumbnail */}
      <div className="relative aspect-[9/16] w-full overflow-hidden bg-muted">
        {video.thumbnail_url ? (
          <Image
            src={video.thumbnail_url}
            alt={video.title}
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 33vw, 25vw"
            className="object-cover transition-transform group-hover:scale-105"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <Play className="h-12 w-12 text-muted-foreground" />
          </div>
        )}

        {/* Platform pill */}
        <div className="absolute left-2 top-2">
          <Badge
            className={cn(
              "border-0 text-white",
              platformColors[video.platform] || "bg-slate-700"
            )}
          >
            {PLATFORM_LABELS[video.platform]}
          </Badge>
        </div>

        {/* Outlier flag */}
        {video.is_outlier && (
          <div className="absolute right-2 top-2">
            <OutlierBadge score={video.outlier_score} isOutlier={video.is_outlier} />
          </div>
        )}

        {/* View count overlay */}
        <div className="absolute bottom-2 left-2 rounded bg-black/70 px-2 py-1 text-xs font-medium text-white">
          <Play className="mr-1 inline h-3 w-3" />
          {formatCompact(video.views)}
        </div>
      </div>

      <CardContent className="space-y-2 p-3">
        {/* Title */}
        <Link
          href={video.url}
          target="_blank"
          rel="noopener noreferrer"
          className="line-clamp-2 text-sm font-semibold hover:underline"
        >
          {video.title}
          <ExternalLink className="ml-1 inline h-3 w-3 opacity-50" />
        </Link>

        {/* Creator */}
        <div className="text-xs text-muted-foreground">
          {video.creator_display_name || video.creator_username}
          {video.creator_followers && (
            <> · {formatCompact(video.creator_followers)} followers</>
          )}
        </div>

        {/* Engagement stats */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Heart className="h-3 w-3" />
            {formatCompact(video.likes)}
          </span>
          <span className="flex items-center gap-1">
            <MessageCircle className="h-3 w-3" />
            {formatCompact(video.comments)}
          </span>
          {video.shares > 0 && (
            <span className="flex items-center gap-1">
              <Share2 className="h-3 w-3" />
              {formatCompact(video.shares)}
            </span>
          )}
        </div>

        {/* AI content brief — outliers with a persisted DB ID only */}
        <ContentBriefButton
          videoId={dbVideoId || null}
          videoTitle={video.title}
          isOutlier={video.is_outlier}
        />

        {/* Schedule a response — outliers with a persisted DB ID only */}
        <ScheduleResponseButton
          videoId={dbVideoId || null}
          isOutlier={video.is_outlier}
        />
      </CardContent>
    </Card>
  );
}
