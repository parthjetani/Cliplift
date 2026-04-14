import type { Metadata } from "next";
import { ThemeProvider } from "@/components/theme/theme-provider";
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
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
    ],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className="min-h-screen bg-background font-sans antialiased transition-colors duration-300"
        suppressHydrationWarning
      >
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
