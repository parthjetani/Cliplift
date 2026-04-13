import type { MetadataRoute } from "next";

import { BLOG_POSTS } from "./(marketing)/blog/posts";

/**
 * Dynamic sitemap for Google indexing.
 * Only includes public marketing pages — dashboard routes are gated by auth.
 * Blog posts are auto-included from the posts registry.
 *
 * Next.js auto-serves this at /sitemap.xml.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://cliplift.com";

  const blogEntries: MetadataRoute.Sitemap = BLOG_POSTS.map((post) => ({
    url: `${baseUrl}/blog/${post.slug}`,
    lastModified: new Date(post.publishedAt),
    changeFrequency: "monthly",
    priority: 0.6,
  }));

  return [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${baseUrl}/compare/virlo`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${baseUrl}/blog`,
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 0.7,
    },
    ...blogEntries,
    {
      url: `${baseUrl}/discover`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.7,
    },
  ];
}
