import Link from "next/link";
import { Sparkles } from "lucide-react";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Public navbar */}
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="container flex h-14 items-center justify-between px-4 sm:h-16 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <span className="text-lg font-bold tracking-tight">Cliplift</span>
          </Link>
          <nav className="flex items-center gap-3 text-sm sm:gap-6">
            <Link
              href="/#pricing"
              className="hidden text-muted-foreground hover:text-foreground sm:inline"
            >
              Pricing
            </Link>
            <Link
              href="/compare/virlo"
              className="hidden text-muted-foreground hover:text-foreground sm:inline"
            >
              vs Virlo
            </Link>
            <Link
              href="/blog"
              className="hidden text-muted-foreground hover:text-foreground sm:inline"
            >
              Blog
            </Link>
            <Link
              href="/discover"
              className="hidden text-muted-foreground hover:text-foreground sm:inline"
            >
              Discover
            </Link>
            <Link
              href="/login"
              className="text-muted-foreground hover:text-foreground"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:opacity-90 sm:px-4 sm:py-2 sm:text-sm"
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      {/* Footer */}
      <footer className="border-t py-8 text-sm text-muted-foreground">
        <div className="container flex flex-col items-center gap-3 px-4 sm:flex-row sm:justify-between sm:px-6">
          <p>© 2026 Cliplift</p>
          <nav className="flex items-center gap-4">
            <Link href="/#pricing" className="hover:text-foreground">
              Pricing
            </Link>
            <Link href="/compare/virlo" className="hover:text-foreground">
              Cliplift vs Virlo
            </Link>
            <Link href="/blog" className="hover:text-foreground">
              Blog
            </Link>
            <Link href="/discover" className="hover:text-foreground">
              Discover
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
