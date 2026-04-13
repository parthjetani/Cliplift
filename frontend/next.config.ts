import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    remotePatterns: [
      // YouTube thumbnails
      { protocol: "https", hostname: "i.ytimg.com" },
      { protocol: "https", hostname: "yt3.ggpht.com" },
      // Instagram CDN
      { protocol: "https", hostname: "scontent.cdninstagram.com" },
      // TikTok CDN
      { protocol: "https", hostname: "p16-sign-va.tiktokcdn.com" },
      // LinkedIn CDN
      { protocol: "https", hostname: "media.licdn.com" },
      // Mock provider placeholder images
      { protocol: "https", hostname: "picsum.photos" },
    ],
  },
};

export default nextConfig;
