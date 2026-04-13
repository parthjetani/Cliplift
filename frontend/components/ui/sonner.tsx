"use client";

import { Toaster as SonnerToaster } from "sonner";

/**
 * Sonner toast renderer — mounted once in the root layout.
 * Uses the default theme which respects the site's light/dark mode.
 */
export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        duration: 5000,
        className: "text-sm",
      }}
    />
  );
}
