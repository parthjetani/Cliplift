"use client";

import { useState, useTransition } from "react";
import { Search, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { VideoCard } from "@/components/discover/video-card";
import { apiPublic, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  PLATFORMS,
  PLATFORM_LABELS,
  type Platform,
  type SearchResponse,
} from "@/lib/types";

interface SearchFormProps {
  initialQuery?: string;
}

export function SearchForm({ initialQuery = "" }: SearchFormProps) {
  const [query, setQuery] = useState(initialQuery);
  const [selectedPlatforms, setSelectedPlatforms] =
    useState<Platform[]>(PLATFORMS);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const togglePlatform = (platform: Platform) => {
    setSelectedPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || selectedPlatforms.length === 0) return;

    setError(null);
    startTransition(async () => {
      try {
        const data = await apiPublic<SearchResponse>("/api/v1/discover/search", {
          method: "POST",
          body: {
            query: query.trim(),
            platforms: selectedPlatforms,
            limit_per_platform: 20,
          },
        });
        setResults(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Something went wrong. Please try again.");
        }
        setResults(null);
      }
    });
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search trends — e.g. fitness hooks"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-11 pl-10 text-base sm:h-12"
              disabled={isPending}
              autoFocus
            />
          </div>
          <Button
            type="submit"
            className="h-11 sm:h-12"
            disabled={isPending || !query.trim() || selectedPlatforms.length === 0}
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching...
              </>
            ) : (
              "Search"
            )}
          </Button>
        </div>

        {/* Platform filter chips */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">
            Platforms:
          </span>
          {PLATFORMS.map((platform) => {
            const isSelected = selectedPlatforms.includes(platform);
            return (
              <button
                key={platform}
                type="button"
                onClick={() => togglePlatform(platform)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  isSelected
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-muted-foreground hover:border-foreground hover:text-foreground"
                )}
              >
                {PLATFORM_LABELS[platform]}
              </button>
            );
          })}
        </div>
      </form>

      {/* Error state */}
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="flex flex-col gap-2 rounded-md border bg-muted/50 px-3 py-2.5 text-sm sm:flex-row sm:flex-wrap sm:items-center sm:gap-3 sm:px-4 sm:py-3">
            <span className="font-medium">
              {results.total} results for &ldquo;{results.query}&rdquo;
            </span>
            {results.outlier_count > 0 && (
              <span className="text-green-600">
                · {results.outlier_count} outlier{results.outlier_count > 1 ? "s" : ""} detected
              </span>
            )}
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground sm:ml-auto sm:gap-3">
              {results.by_platform.map((p) => (
                <span key={p.platform}>
                  {PLATFORM_LABELS[p.platform]}: {p.count}
                </span>
              ))}
            </div>
          </div>

          {/* Video grid */}
          {results.videos.length === 0 ? (
            <div className="rounded-md border border-dashed py-12 text-center text-muted-foreground">
              No results found. Try a different query.
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
              {results.videos.map((video) => (
                <VideoCard key={`${video.platform}-${video.platform_video_id}`} video={video} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
