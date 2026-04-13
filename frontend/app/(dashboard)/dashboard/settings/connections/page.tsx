"use client";

import { useEffect, useState, useTransition } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  Link2,
  Loader2,
  Trash2,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/page-header";
import { PlatformBadge } from "@/components/shared/platform-badge";
import { ConfirmDelete } from "@/components/shared/confirm-delete";
import { apiAuth, ApiError, showApiError } from "@/lib/api";
import {
  PLATFORMS,
  PLATFORM_LABELS,
  type AuthorizeResponse,
  type Platform,
  type PlatformConnection,
} from "@/lib/types";

function ConnectionsContent() {
  const searchParams = useSearchParams();
  const justConnected = searchParams.get("connected") === "1";

  const [connections, setConnections] = useState<PlatformConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingPlatform, setPendingPlatform] = useState<Platform | null>(null);
  const [, startTransition] = useTransition();

  const refresh = async () => {
    try {
      const data = await apiAuth<PlatformConnection[]>("/api/v1/connections");
      setConnections(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleConnect = (platform: Platform) => {
    setPendingPlatform(platform);
    startTransition(async () => {
      try {
        const auth = await apiAuth<AuthorizeResponse>(
          `/api/v1/connections/${platform}/authorize`,
          { method: "POST" }
        );
        // Redirect the browser to the authorize URL.
        // Mock provider: this is our own callback URL with code+state.
        // Real provider: this is Google/Meta's consent screen.
        window.location.href = auth.authorize_url;
      } catch (err) {
        showApiError(err);
        setError(err instanceof ApiError ? err.message : "Failed to start OAuth");
        setPendingPlatform(null);
      }
    });
  };

  const handleDisconnect = (id: string) => {
    startTransition(async () => {
      try {
        await apiAuth(`/api/v1/connections/${id}`, { method: "DELETE" });
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to disconnect");
      }
    });
  };

  // Map platform → connection (if any)
  const byPlatform = new Map<Platform, PlatformConnection>(
    connections.map((c) => [c.platform, c])
  );

  return (
    <div className="container max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/dashboard/settings">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="h-4 w-4" />
          Back to settings
        </Button>
      </Link>

      <PageHeader
        title="Platform Connections"
        description="Connect your social accounts to publish directly from Cliplift."
      />

      {justConnected && (
        <div className="mb-6 flex items-center gap-2 rounded-md border border-green-500/50 bg-green-500/10 p-3 text-sm text-green-700">
          <CheckCircle2 className="h-4 w-4" />
          Connection successful.
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {PLATFORMS.map((platform) => {
            const connection = byPlatform.get(platform);
            const isPending = pendingPlatform === platform;

            return (
              <Card key={platform}>
                <CardContent className="flex items-center justify-between gap-4 p-4">
                  <div className="flex items-center gap-3">
                    <PlatformBadge platform={platform} />
                    {connection ? (
                      <div>
                        <p className="font-medium">
                          {connection.platform_username || "Connected"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Connected{" "}
                          {new Date(connection.connected_at).toLocaleDateString()}
                          {connection.is_expired && (
                            <span className="ml-2 text-amber-600">
                              · token expired
                            </span>
                          )}
                        </p>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Not connected
                      </p>
                    )}
                  </div>

                  {connection ? (
                    <div className="flex items-center gap-2">
                      <Badge variant="success">
                        <CheckCircle2 className="mr-1 h-3 w-3" />
                        Connected
                      </Badge>
                      <ConfirmDelete
                        title={`Disconnect ${PLATFORM_LABELS[platform]}?`}
                        description="You'll need to reconnect to publish to this platform again. Your encrypted tokens will be permanently deleted."
                        confirmText="Disconnect"
                        onConfirm={() => handleDisconnect(connection.id)}
                      >
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Disconnect"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </ConfirmDelete>
                    </div>
                  ) : (
                    <Button
                      onClick={() => handleConnect(platform)}
                      disabled={isPending}
                    >
                      {isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Redirecting...
                        </>
                      ) : (
                        <>Connect {PLATFORM_LABELS[platform]}</>
                      )}
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <p className="mt-6 text-xs text-muted-foreground">
        Tokens are AES-256 encrypted before being stored. Cliplift only requests
        the minimum scopes needed for publishing and reading post analytics.
      </p>
    </div>
  );
}

export default function ConnectionsPage() {
  return (
    <Suspense fallback={<div className="container py-8">Loading...</div>}>
      <ConnectionsContent />
    </Suspense>
  );
}
