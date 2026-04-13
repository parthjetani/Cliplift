"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Hash, Plus, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { apiAuth, ApiError } from "@/lib/api";
import type { Niche, PaginatedResponse } from "@/lib/types";

export default function NichesPage() {
  const [data, setData] = useState<PaginatedResponse<Niche> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const result = await apiAuth<PaginatedResponse<Niche>>(
          "/api/v1/niches?limit=50"
        );
        setData(result);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const action = (
    <Link href="/dashboard/niches/new">
      <Button>
        <Plus className="h-4 w-4" />
        Create niche
      </Button>
    </Link>
  );

  return (
    <div className="container max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader
        title="Niches"
        description="Topics you're tracking. The auto-discovery worker searches your keywords across all configured platforms hourly."
        action={action}
      />

      {loading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {[...Array(2)].map((_, i) => (
            <Skeleton key={i} className="h-36 w-full" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={Hash}
          title="No niches yet"
          description="Create your first niche to start auto-discovering trending content in your space."
          action={action}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {data.items.map((niche) => (
            <Link key={niche.id} href={`/dashboard/niches/${niche.id}`}>
              <Card className="h-full transition-shadow hover:shadow-md">
                <CardContent className="p-5">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-lg font-semibold">{niche.name}</h3>
                    {!niche.is_active && (
                      <Badge variant="secondary">Paused</Badge>
                    )}
                  </div>

                  <div className="mb-3 flex flex-wrap gap-1">
                    {niche.keywords.slice(0, 5).map((kw) => (
                      <Badge key={kw} variant="outline" className="text-xs">
                        {kw}
                      </Badge>
                    ))}
                    {niche.keywords.length > 5 && (
                      <Badge variant="outline" className="text-xs">
                        +{niche.keywords.length - 5}
                      </Badge>
                    )}
                  </div>

                  <div className="mb-2 flex flex-wrap gap-1">
                    {niche.platforms.map((p) => (
                      <PlatformBadge key={p} platform={p} className="text-xs" />
                    ))}
                  </div>

                  <p className="mt-3 text-xs text-muted-foreground">
                    {niche.last_analyzed_at
                      ? `Last analyzed ${new Date(niche.last_analyzed_at).toLocaleString()}`
                      : "Awaiting first analysis"}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
