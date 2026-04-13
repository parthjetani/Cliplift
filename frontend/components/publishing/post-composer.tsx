"use client";

import { useState } from "react";
import Image from "next/image";
import { Sparkles } from "lucide-react";

import {
  UploadDropzone,
  type UploadedFile,
} from "@/components/publishing/upload-dropzone";
import { ScheduledPostForm } from "@/components/publishing/scheduled-post-form";
import { Card, CardContent } from "@/components/ui/card";
import { formatCompact } from "@/lib/utils";
import type { PlatformConnection, Video } from "@/lib/types";

interface PostComposerProps {
  connections: PlatformConnection[];
  /** Pre-filled when the user came from /discover via "Schedule a response". */
  inspiredBy?: Video | null;
}

/**
 * Two-column composer:
 *   left  — upload dropzone + uploaded-file state
 *   right — scheduled post form (title, description, hashtags, schedule time)
 *
 * The "Inspired by" preview card spans both columns at the top, only when the
 * user came from a /discover outlier card.
 */
export function PostComposer({ connections, inspiredBy }: PostComposerProps) {
  const [uploaded, setUploaded] = useState<UploadedFile | null>(null);

  return (
    <div className="space-y-6">
      {inspiredBy && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="flex items-start gap-4 p-4">
            <div className="rounded-md bg-primary/10 p-2">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium uppercase tracking-wide text-primary">
                Inspired by
              </p>
              <p className="mt-1 line-clamp-2 text-sm font-semibold">
                {inspiredBy.title || "Untitled video"}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {inspiredBy.platform} ·{" "}
                {formatCompact(inspiredBy.latest_views)} views
                {inspiredBy.outlier_score &&
                  ` · ${inspiredBy.outlier_score.toFixed(1)}σ outlier`}
              </p>
            </div>
            {inspiredBy.thumbnail_url && (
              <div className="relative h-16 w-12 shrink-0 overflow-hidden rounded">
                <Image
                  src={inspiredBy.thumbnail_url}
                  alt={inspiredBy.title || ""}
                  fill
                  sizes="48px"
                  className="object-cover"
                  unoptimized
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-2">
          <p className="text-sm font-medium">Video file</p>
          <UploadDropzone
            uploaded={uploaded}
            onUploaded={setUploaded}
            onCleared={() => setUploaded(null)}
          />
        </div>

        <div>
          <ScheduledPostForm
            connections={connections}
            uploaded={uploaded}
            inspiredByVideoId={inspiredBy?.id}
          />
        </div>
      </div>
    </div>
  );
}
