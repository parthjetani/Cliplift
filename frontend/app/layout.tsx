import type { Metadata } from "next";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Cliplift — Short-form video analytics + publishing",
    template: "%s | Cliplift",
  },
  description:
    "Discover what's going viral, publish your response, measure the results. One tool, flat rate, no credits. The anti-credit alternative to Virlo.",
  keywords: [
    "short-form video analytics",
    "tiktok analytics",
    "youtube shorts analytics",
    "linkedin video analytics",
    "instagram reels analytics",
    "virlo alternative",
  ],
  authors: [{ name: "Cliplift" }],
  openGraph: {
    title: "Cliplift — Short-form video analytics + publishing",
    description:
      "Track viral content across YouTube, Instagram, LinkedIn, and TikTok. Flat rate. No credits.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/*
        suppressHydrationWarning on <body> silences false positives from
        browser extensions (Grammarly, Dark Reader, LastPass, etc.) that
        inject attributes into the body before React loads.
      */}
      <body
        className="min-h-screen bg-background font-sans antialiased"
        suppressHydrationWarning
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
