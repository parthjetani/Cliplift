import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Calendar } from "lucide-react";

import { BLOG_POSTS, getPost } from "../posts";

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return BLOG_POSTS.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return {};
  return {
    title: post.title,
    description: post.description,
    openGraph: {
      title: post.title,
      description: post.description,
      type: "article",
      publishedTime: post.publishedAt,
      authors: [post.author],
    },
  };
}

/**
 * Minimal Markdown-to-JSX renderer. Handles headings, paragraphs, code
 * blocks, inline code, bold, tables, lists, and links. Good enough for
 * our blog posts without pulling in a full MDX pipeline.
 */
function renderMarkdown(content: string) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      elements.push(
        <pre
          key={elements.length}
          className="my-4 overflow-x-auto rounded-lg bg-muted p-4 text-sm"
        >
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    // Table
    if (line.includes("|") && line.trim().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].includes("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      const rows = tableLines
        .filter((r) => !r.match(/^\|[\s-|]+\|$/))
        .map((r) =>
          r
            .split("|")
            .filter(Boolean)
            .map((c) => c.trim())
        );
      if (rows.length > 0) {
        const [header, ...body] = rows;
        elements.push(
          <div key={elements.length} className="my-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  {header.map((h, j) => (
                    <th
                      key={j}
                      className="px-3 py-2 text-left font-semibold"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {body.map((row, ri) => (
                  <tr key={ri} className="border-b last:border-0">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-2">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      continue;
    }

    // Headings
    if (line.startsWith("## ")) {
      elements.push(
        <h2 key={elements.length} className="mb-3 mt-8 text-xl font-bold">
          {line.slice(3)}
        </h2>
      );
      i++;
      continue;
    }
    if (line.startsWith("### ")) {
      elements.push(
        <h3 key={elements.length} className="mb-2 mt-6 text-lg font-semibold">
          {line.slice(4)}
        </h3>
      );
      i++;
      continue;
    }

    // List items
    if (line.match(/^\d+\.\s/) || line.startsWith("- ")) {
      const listItems: string[] = [];
      const isOrdered = !!line.match(/^\d+\.\s/);
      while (
        i < lines.length &&
        (lines[i].match(/^\d+\.\s/) || lines[i].startsWith("- "))
      ) {
        listItems.push(
          lines[i].replace(/^\d+\.\s/, "").replace(/^-\s/, "")
        );
        i++;
      }
      const Tag = isOrdered ? "ol" : "ul";
      elements.push(
        <Tag
          key={elements.length}
          className={`my-3 space-y-1 pl-5 text-sm leading-relaxed text-muted-foreground ${isOrdered ? "list-decimal" : "list-disc"}`}
        >
          {listItems.map((item, j) => (
            <li key={j}>{renderInline(item)}</li>
          ))}
        </Tag>
      );
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Paragraph
    elements.push(
      <p
        key={elements.length}
        className="my-3 text-sm leading-relaxed text-muted-foreground"
      >
        {renderInline(line)}
      </p>
    );
    i++;
  }

  return elements;
}

function renderInline(text: string): React.ReactNode {
  // Bold + inline code
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  return (
    <article className="container max-w-3xl px-4 py-12 sm:px-6 sm:py-20">
      <Link
        href="/blog"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3 w-3" />
        All posts
      </Link>

      <header>
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
          <span>{post.author}</span>
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
          {post.title}
        </h1>
        <p className="mt-2 text-muted-foreground">{post.description}</p>
        <div className="mt-4 flex flex-wrap gap-1">
          {post.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border px-2.5 py-0.5 text-xs font-medium"
            >
              {tag}
            </span>
          ))}
        </div>
      </header>

      <hr className="my-8" />

      <div className="prose-custom">{renderMarkdown(post.content)}</div>

      <hr className="my-8" />

      <div className="text-center">
        <p className="text-sm text-muted-foreground">
          Want to see this in action?{" "}
          <Link href="/discover" className="font-medium text-primary hover:underline">
            Try the search for free
          </Link>{" "}
          or{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">
            start your 7-day trial
          </Link>
          .
        </p>
      </div>
    </article>
  );
}
