"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, User as UserIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MobileNav } from "@/components/layout/mobile-nav";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { createClient } from "@/lib/supabase/client";

interface HeaderProps {
  email?: string | null;
}

export function Header({ email }: HeaderProps) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  const handleSignOut = async () => {
    setSigningOut(true);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  };

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-4 md:h-16 md:px-6">
      <div className="flex items-center gap-3">
        {/* Mobile: hamburger + logo */}
        <MobileNav />
        <span className="text-lg font-bold tracking-tight md:hidden">
          Cliplift
        </span>
      </div>

      <div className="flex items-center gap-1 sm:gap-2">
        {email && (
          <div className="hidden items-center gap-2 text-sm text-muted-foreground lg:flex">
            <UserIcon className="h-4 w-4" />
            <span className="max-w-[200px] truncate">{email}</span>
          </div>
        )}
        <ThemeToggle />
        <Button
          variant="ghost"
          size="sm"
          onClick={handleSignOut}
          disabled={signingOut}
        >
          <LogOut className="h-4 w-4" />
          <span className="ml-2 hidden sm:inline">Sign out</span>
        </Button>
      </div>
    </header>
  );
}
