"use client";

import { useTheme } from "next-themes";
import { Toaster as SonnerToaster } from "sonner";

/**
 * Sonner toast renderer — mounted once in the root layout.
 * Reads the current theme from next-themes so toasts match dark/light mode.
 */
export function Toaster() {
  const { resolvedTheme } = useTheme();

  return (
    <SonnerToaster
      position="bottom-right"
      richColors
      closeButton
      theme={resolvedTheme === "dark" ? "dark" : "light"}
      toastOptions={{
        duration: 5000,
        className: "text-sm",
      }}
    />
  );
}
