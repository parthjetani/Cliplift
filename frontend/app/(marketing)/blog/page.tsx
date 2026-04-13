import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Calendar } from "lucide-react";

import { BLOG_POSTS } from "./posts";

export const metadata: Metadata = {
  title: "Blog — Engineering & product insights",
  description:
    "Technical deep dives, product updates, and behind-the-scenes engineering from the Cliplift team.",
};

export default function BlogIndexPage() {
  return (
    <div className="container max-w-3xl px-4 py-12 sm:px-6 sm:py-20">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Blog</h1>
      <p className="mt-2 text-muted-foreground">
        Engineering deep dives and product updates from the Cliplift team.
      </p>

      <div className="mt-10 divide-y">
        {BLOG_POSTS.map((post) => (
          <article key={post.slug} className="py-8 first:pt-0">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Calendar className="h-3 w-3" />
              <time dateTime={post.publishedAt}>
                {new Date(post.publishedAt).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </time>
              <span className="text-border">|</span>
              {post.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border px-2 py-0.5 text-[10px] font-medium"
                >
                  {tag}
                </span>
              ))}
            </div>
            <Link href={`/blog/${post.slug}`} className="group">
              <h2 className="mt-2 text-xl font-semibold group-hover:text-primary">
                {post.title}
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {post.description}
              </p>
              <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary">
                Read more
                <ArrowRight className="h-3 w-3" />
              </span>
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
