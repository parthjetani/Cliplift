"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiAuth, ApiError, showApiError } from "@/lib/api";
import {
  PLATFORM_LABELS,
  type PlatformConnection,
  type ScheduledPostCreate,
  type ScheduledPostResponse,
} from "@/lib/types";

import type { UploadedFile } from "@/components/publishing/upload-dropzone";

interface ScheduledPostFormProps {
  /** The team's existing platform connections (fetched server-side). */
  connections: PlatformConnection[];
  /** Set after the upload dropzone completes — required to enable submit. */
  uploaded: UploadedFile | null;
  /** Pre-filled when the user came from /discover via "Schedule a response". */
  inspiredByVideoId?: string | null;
  /** Pre-filled title (e.g., from a content brief or "Inspired by" video). */
  initialTitle?: string;
}

/**
 * Default scheduled time = 1 hour from now, rounded down to the next minute.
 * Returned in `<input type="datetime-local">` format (no Z, no seconds).
 */
function defaultScheduledFor(): string {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  d.setSeconds(0, 0);
  // YYYY-MM-DDTHH:MM in the user's local time
  const tzOffset = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
}

export function ScheduledPostForm({
  connections,
  uploaded,
  inspiredByVideoId,
  initialTitle = "",
}: ScheduledPostFormProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const [connectionId, setConnectionId] = useState<string>(
    connections[0]?.id ?? ""
  );
  const [title, setTitle] = useState(initialTitle);
  const [description, setDescription] = useState("");
  const [hashtagsRaw, setHashtagsRaw] = useState("");
  const [scheduledFor, setScheduledFor] = useState(defaultScheduledFor);

  const selectedConnection = connections.find((c) => c.id === connectionId);
  const canSubmit = Boolean(
    uploaded && selectedConnection && title.trim() && !isPending
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!uploaded) {
      setError("Upload a video first");
      return;
    }
    if (!selectedConnection) {
      setError("Pick a connected account");
      return;
    }

    const hashtags = hashtagsRaw
      .split(/[\s,]+/)
      .map((h) => h.trim().replace(/^#/, ""))
      .filter(Boolean);
    if (hashtags.length > 30) {
      setError("Maximum 30 hashtags");
      return;
    }

    // datetime-local is local-time without TZ — convert to ISO with offset
    const scheduledIso = new Date(scheduledFor).toISOString();

    const payload: ScheduledPostCreate = {
      connection_id: selectedConnection.id,
      platform: selectedConnection.platform,
      file_key: uploaded.file_key,
      title: title.trim(),
      description: description.trim() || null,
      hashtags: hashtags.length > 0 ? hashtags : null,
      scheduled_for: scheduledIso,
      inspired_by_video_id: inspiredByVideoId || null,
    };

    startTransition(async () => {
      try {
        const post = await apiAuth<ScheduledPostResponse>(
          "/api/v1/publishing/scheduled-posts",
          { method: "POST", body: payload }
        );
        router.push(`/dashboard/posts/${post.id}`);
      } catch (e) {
        showApiError(e);
        setError(e instanceof ApiError ? e.message : "Failed to schedule post");
      }
    });
  };

  if (connections.length === 0) {
    return (
      <div className="rounded-md border border-amber-500/50 bg-amber-500/10 p-4 text-sm">
        <p className="font-medium">No connected accounts</p>
        <p className="mt-1 text-muted-foreground">
          Connect a YouTube or Instagram account before scheduling a post.
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={() => router.push("/dashboard/settings/connections")}
        >
          Connect an account
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="post-connection">Publish to</Label>
        <select
          id="post-connection"
          value={connectionId}
          onChange={(e) => setConnectionId(e.target.value)}
          disabled={isPending}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {PLATFORM_LABELS[c.platform]} —{" "}
              {c.platform_username || c.platform_user_id || "(no name)"}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="post-title">Title</Label>
        <Input
          id="post-title"
          placeholder="Catchy title for your video"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          maxLength={512}
          disabled={isPending}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="post-description">Description</Label>
        <Textarea
          id="post-description"
          placeholder="Optional caption / description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          disabled={isPending}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="post-hashtags">Hashtags</Label>
        <Input
          id="post-hashtags"
          placeholder="#fitness #morning (space or comma separated)"
          value={hashtagsRaw}
          onChange={(e) => setHashtagsRaw(e.target.value)}
          disabled={isPending}
        />
        <p className="text-xs text-muted-foreground">
          Max 30 hashtags. The leading # is optional.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="post-scheduled-for">Schedule for</Label>
        <Input
          id="post-scheduled-for"
          type="datetime-local"
          value={scheduledFor}
          onChange={(e) => setScheduledFor(e.target.value)}
          required
          disabled={isPending}
        />
        <p className="text-xs text-muted-foreground">
          Local time. The publish worker checks every 5 minutes.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.back()}
          disabled={isPending}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={!canSubmit}>
          {isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Scheduling...
            </>
          ) : (
            "Schedule post"
          )}
        </Button>
      </div>
    </form>
  );
}
