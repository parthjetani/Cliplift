import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Refresh the Supabase session on every request.
 *
 * Called from `middleware.ts` (Next.js root middleware). Without this, the
 * server-side Supabase client returns stale auth state because Server
 * Components cannot set cookies themselves.
 *
 * Also handles redirects:
 * - Unauthenticated users hitting /dashboard/* → redirect to /login
 */
export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(
          cookiesToSet: { name: string; value: string; options?: CookieOptions }[]
        ) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // IMPORTANT: getUser() (not getSession()) — getUser revalidates the JWT
  // against Supabase Auth, while getSession only reads cookies.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;

  // Protected routes — redirect unauthenticated users to /login
  const isProtected =
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/discover/saved") ||
    pathname.startsWith("/creators") ||
    pathname.startsWith("/niches") ||
    pathname.startsWith("/schedule") ||
    pathname.startsWith("/analytics") ||
    pathname.startsWith("/settings");

  if (isProtected && !user) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  // Logged-in users hitting /login or /register → bounce to dashboard
  if (user && (pathname === "/login" || pathname === "/register")) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
