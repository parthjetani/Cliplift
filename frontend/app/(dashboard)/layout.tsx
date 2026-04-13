import { redirect } from "next/navigation";

import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { TrialBannerWrapper } from "@/components/billing/trial-banner-wrapper";
import { createClient } from "@/lib/supabase/server";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex h-[100dvh] bg-background">
      {/* Desktop sidebar — hidden on mobile, mobile-nav.tsx handles it */}
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header email={user.email} />
        <TrialBannerWrapper />
        <main className="flex-1 overflow-y-auto overflow-x-hidden">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
