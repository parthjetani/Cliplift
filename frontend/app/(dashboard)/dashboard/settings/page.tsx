"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CreditCard, Link2, User, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { apiAuth, ApiError } from "@/lib/api";
import type { ProfileResponse } from "@/lib/types";

export default function SettingsPage() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiAuth<ProfileResponse>("/api/v1/profile");
        setProfile(data);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="container max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader title="Settings" description="Manage your account and connections." />

      {/* Account card */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <User className="h-4 w-4" />
            Account
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-16 w-full" />
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : profile ? (
            <div className="space-y-2 text-sm">
              <Field label="Email" value={profile.email} />
              {profile.name && <Field label="Name" value={profile.name} />}
              <Field
                label="Member since"
                value={new Date(profile.created_at).toLocaleDateString()}
              />
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Billing card */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <CreditCard className="h-4 w-4" />
            Billing & Plan
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">
            View your current plan, usage meters, and upgrade options.
          </p>
          <Link
            href="/dashboard/settings/billing"
            className="text-sm font-medium text-primary hover:underline"
          >
            Manage billing →
          </Link>
        </CardContent>
      </Card>

      {/* Connections card */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Link2 className="h-4 w-4" />
            Platform Connections
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">
            Connect YouTube, Instagram, and other platforms to publish content
            directly from Cliplift.
          </p>
          <Link
            href="/dashboard/settings/connections"
            className="text-sm font-medium text-primary hover:underline"
          >
            Manage connections →
          </Link>
        </CardContent>
      </Card>

      {/* Team card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Users className="h-4 w-4" />
            Team Members
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">
            Invite team members and manage workspace access.
          </p>
          <Link
            href="/dashboard/settings/team"
            className="text-sm font-medium text-primary hover:underline"
          >
            Manage team →
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b py-2 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
