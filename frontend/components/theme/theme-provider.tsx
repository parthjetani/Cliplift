"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

/**
 * Wraps next-themes ThemeProvider. Mounted in the root layout.
 * Uses `class` strategy (Tailwind's darkMode: ["class"]) and defaults
 * to the system preference.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange={false}
    >
      {children}
    </NextThemesProvider>
  );
}
