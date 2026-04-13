"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader } from "@/components/shared/page-header";
import { apiAuth, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  PLATFORMS,
  PLATFORM_LABELS,
  type Niche,
  type Platform,
} from "@/lib/types";

export default function NewNichePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [keywordsRaw, setKeywordsRaw] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] =
    useState<Platform[]>(PLATFORMS);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const togglePlatform = (p: Platform) => {
    setSelectedPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const keywords = keywordsRaw
      .split(/[\n,]/)
      .map((k) => k.trim())
      .filter(Boolean);

    if (keywords.length === 0) {
      setError("At least one keyword is required");
      return;
    }
    if (keywords.length > 20) {
      setError("Maximum 20 keywords");
      return;
    }
    if (selectedPlatforms.length === 0) {
      setError("Select at least one platform");
      return;
    }

    startTransition(async () => {
      try {
        const niche = await apiAuth<Niche>("/api/v1/niches", {
          method: "POST",
          body: {
            name: name.trim(),
            keywords,
            platforms: selectedPlatforms,
          },
        });
        router.push(`/dashboard/niches/${niche.id}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to create");
      }
    });
  };

  return (
    <div className="container max-w-2xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/niches">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back to niches
        </Button>
      </Link>

      <PageHeader
        title="Create niche"
        description="Define keywords to track. The discovery worker searches them every hour and surfaces outliers in your feed."
      />

      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="niche-name">Name</Label>
              <Input
                id="niche-name"
                placeholder="e.g. Fitness Shorts, B2B SaaS Marketing"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={255}
                disabled={isPending}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="niche-keywords">Keywords</Label>
              <Textarea
                id="niche-keywords"
                placeholder="One per line, or comma-separated. Example: fitness, workout, gym, hiit"
                value={keywordsRaw}
                onChange={(e) => setKeywordsRaw(e.target.value)}
                rows={4}
                required
                disabled={isPending}
              />
              <p className="text-xs text-muted-foreground">
                1-20 keywords. The worker joins them with spaces and searches
                each platform.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Platforms</Label>
              <div className="flex flex-wrap gap-2">
                {PLATFORMS.map((p) => {
                  const selected = selectedPlatforms.includes(p);
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => togglePlatform(p)}
                      disabled={isPending}
                      className={cn(
                        "rounded-full border px-3 py-1.5 text-xs font-medium transition",
                        selected
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background text-muted-foreground hover:border-foreground hover:text-foreground"
                      )}
                    >
                      {PLATFORM_LABELS[p]}
                    </button>
                  );
                })}
              </div>
            </div>

            {error && (
              <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <Link href="/dashboard/niches">
                <Button type="button" variant="outline" disabled={isPending}>
                  Cancel
                </Button>
              </Link>
              <Button type="submit" disabled={isPending}>
                {isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create niche"
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
