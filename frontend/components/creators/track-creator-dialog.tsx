"use client";

import { useState, useTransition } from "react";
import { Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiAuth, ApiError, showApiError } from "@/lib/api";
import type { Platform, TrackedCreator } from "@/lib/types";

const PLATFORMS: { value: Platform; label: string }[] = [
  { value: "youtube", label: "YouTube" },
  { value: "instagram", label: "Instagram" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "tiktok", label: "TikTok" },
];

interface TrackCreatorDialogProps {
  /**
   * Called after a successful track. Use this to re-fetch the parent
   * component's data — `router.refresh()` does NOT re-run client useEffect
   * hooks, so list components must explicitly re-fetch.
   */
  onSuccess?: () => void;
}

export function TrackCreatorDialog({ onSuccess }: TrackCreatorDialogProps = {}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"url" | "explicit">("url");
  const [url, setUrl] = useState("");
  const [platform, setPlatform] = useState<Platform>("youtube");
  const [platformId, setPlatformId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    startTransition(async () => {
      try {
        const body =
          mode === "url"
            ? { url: url.trim() }
            : { platform, platform_id: platformId.trim() };

        await apiAuth<TrackedCreator>("/api/v1/creators/track", {
          method: "POST",
          body,
        });

        // Reset and close
        setUrl("");
        setPlatformId("");
        setOpen(false);
        onSuccess?.();
      } catch (err) {
        showApiError(err);
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Failed to track creator");
        }
      }
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4" />
          Track creator
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Track a new creator</DialogTitle>
          <DialogDescription>
            Add a creator to follow. We&apos;ll snapshot their metrics daily and
            flag outlier videos.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Mode toggle */}
          <div className="flex gap-2 rounded-md bg-muted p-1 text-sm">
            <button
              type="button"
              onClick={() => setMode("url")}
              className={`flex-1 rounded px-3 py-1.5 font-medium transition ${
                mode === "url" ? "bg-background shadow-sm" : "text-muted-foreground"
              }`}
            >
              By URL
            </button>
            <button
              type="button"
              onClick={() => setMode("explicit")}
              className={`flex-1 rounded px-3 py-1.5 font-medium transition ${
                mode === "explicit"
                  ? "bg-background shadow-sm"
                  : "text-muted-foreground"
              }`}
            >
              By platform + ID
            </button>
          </div>

          {mode === "url" ? (
            <div className="space-y-2">
              <Label htmlFor="creator-url">Creator URL</Label>
              <Input
                id="creator-url"
                type="url"
                placeholder="https://youtube.com/@creator or tiktok.com/@user"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
                disabled={isPending}
              />
              <p className="text-xs text-muted-foreground">
                Supports YouTube channel URLs, TikTok @handles, Instagram
                profiles, and LinkedIn /in/ URLs.
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <Label htmlFor="creator-platform">Platform</Label>
                <select
                  id="creator-platform"
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value as Platform)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  disabled={isPending}
                >
                  {PLATFORMS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="creator-id">Platform user ID</Label>
                <Input
                  id="creator-id"
                  placeholder="Channel ID, @username, etc."
                  value={platformId}
                  onChange={(e) => setPlatformId(e.target.value)}
                  required
                  disabled={isPending}
                />
              </div>
            </>
          )}

          {error && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Tracking...
                </>
              ) : (
                "Track creator"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
