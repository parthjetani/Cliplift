/**
 * Blog post metadata + content. Stored as code (not a CMS) because there
 * are only a handful of posts and they're tightly coupled to the product.
 * Migrate to MDX or a headless CMS when the post count exceeds ~20.
 */

export interface BlogPost {
  slug: string;
  title: string;
  description: string;
  publishedAt: string;
  author: string;
  tags: string[];
  /** Raw markdown-ish content rendered in the blog post page. */
  content: string;
}

export const BLOG_POSTS: BlogPost[] = [
  {
    slug: "how-we-built-cliplift",
    title: "How We Built Cliplift: Architecture of a Mock-First SaaS",
    description:
      "A deep dive into the technical architecture behind Cliplift — FastAPI, Next.js, mock-first design, and why every external integration works without an API key.",
    publishedAt: "2026-04-13",
    author: "Cliplift Engineering",
    tags: ["engineering", "architecture", "fastapi", "nextjs"],
    content: `## The problem with building integrations first

Most SaaS products can't run locally without a dozen API keys, a Stripe test account, and a prayer. We decided early that Cliplift would be different: **the full stack runs end-to-end with a blank .env file**.

This isn't just a developer convenience — it's an architectural constraint that forces clean abstractions.

## The mock-first pattern

Every external service in Cliplift follows the same pattern:

1. **Protocol/ABC** (base.py) — defines the interface
2. **Real implementation** — wraps the external SDK/API
3. **Mock implementation** — deterministic fake data, no network calls
4. **Factory function** — picks real vs mock based on env vars

The factory runs once at startup and stashes the result on \`app.state\`:

\`\`\`python
app.state.data_provider_router = build_data_router(settings)
app.state.ai_client = get_ai_client(settings)
app.state.storage = build_storage(settings)
app.state.publisher_router = build_publisher_router(settings)
app.state.stripe_client = build_stripe_client(settings)
\`\`\`

Routes pull these via FastAPI \`Depends()\` — no global state, fully testable.

## Stack choices

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python 3.12) | Async, typed, auto-generated OpenAPI |
| Frontend | Next.js 15 (App Router) | SSR + client components, great DX |
| Database | Supabase Postgres | Free tier, Auth built in |
| Auth | Supabase JWT | No custom register/login — frontend uses the SDK |
| Workers | QStash (Upstash) | HTTP-triggered, not long-running processes |
| Storage | Supabase Storage | Presigned URLs, browser uploads directly |
| Payments | Stripe | Mock client when STRIPE_SECRET_KEY is empty |

## Module pattern

Every domain (creators, videos, discovery, publishing, billing) follows the same 4-file shape:

\`\`\`
domain/
  models.py     # SQLAlchemy ORM
  schemas.py    # Pydantic request/response
  service.py    # Business logic
  routes.py     # FastAPI router (thin)
\`\`\`

Routes call services. Services own DB queries. This separation means we can unit-test business logic without spinning up an HTTP server.

## What we learned

1. **Mock-first is a chain** — if the OAuth provider is mocked, the publisher that depends on those tokens must also be mocked. We missed this initially and got 401s from YouTube in dev.

2. **\`LIMIT N\` without \`ORDER BY\` is a latent bug** — our discover-trends worker hit this after accumulating >100 niches. Now every limited query has explicit ordering.

3. **Plan enforcement belongs in the route layer**, not middleware. Write endpoints use \`require_active_plan\`; GET endpoints skip it entirely. Cancelled users can still read their data.

4. **299 tests run against a real Postgres** — no mocked DB. Slower but catches real constraint violations, encoding issues, and migration problems.

## Open source

The full codebase, including 11 documentation files covering architecture, API reference, database schema, and more, is available on GitHub.`,
  },
  {
    slug: "building-multi-platform-video-analytics",
    title: "Building a Multi-Platform Video Analytics Pipeline",
    description:
      "How Cliplift's DataProviderRouter abstracts YouTube, Instagram, TikTok, and LinkedIn behind a single interface — and why we buy data instead of scraping.",
    publishedAt: "2026-04-13",
    author: "Cliplift Engineering",
    tags: ["engineering", "data", "analytics", "api"],
    content: `## The market runs on third-party data

Every video analytics tool — including Virlo — relies on scraping or third-party data APIs for competitive intelligence. The constraint isn't unique to us; it's structural to the market.

Our approach: **buy data until $5K MRR, then build scrapers for high-volume platforms**. The DataProviderRouter abstraction makes this swap invisible to the rest of the codebase.

## The DataProviderRouter

A registry that dispatches calls to per-platform adapters:

\`\`\`python
router = DataProviderRouter()
router.register(YouTubeProvider(api_key="..."))
router.register(NetrowsProvider(api_key="..."))
router.register(MockDataProvider(Platform.TIKTOK))

# Multi-platform parallel search
results = await router.search_videos("fitness", [Platform.YOUTUBE, Platform.LINKEDIN])
\`\`\`

Key behaviors:
- **Parallel execution** — all platforms searched simultaneously via \`asyncio.gather\`
- **Partial results** — a failed provider returns an empty list, not an error
- **Mock fallback** — missing API keys automatically use deterministic fake data

## The DataProvider interface

Every adapter implements three methods:

\`\`\`python
class DataProvider(ABC):
    async def search_videos(self, query: str, limit: int = 20) -> list[VideoSearchResult]
    async def get_creator(self, platform_id: str) -> CreatorProfile | None
    async def get_video_metrics(self, platform_video_id: str) -> VideoMetrics | None
\`\`\`

The return types (\`VideoSearchResult\`, \`CreatorProfile\`, \`VideoMetrics\`) are platform-agnostic Pydantic models. YouTube returns views as an integer; so does TikTok; so does LinkedIn. The normalization happens inside each adapter, not in the consuming code.

## Our data sources

| Platform | Provider | Cost | Why |
|---|---|---|---|
| YouTube | YouTube Data API v3 | Free (10K quota/day) | Official, reliable |
| LinkedIn | Netrows | ~$53/mo | **The differentiator** — nobody else tracks LinkedIn video |
| TikTok | Data365 | $99/mo | Comprehensive video + creator data |
| Instagram | Data365 | Included | Same provider as TikTok |

Total: ~$155/mo for 4-platform competitive intelligence.

## Outlier detection

Every search result gets a Z-score:

\`\`\`
baseline = median(views across all results in this niche)
std_dev = std_deviation(views)
outlier_score = (video_views - baseline) / std_dev
is_outlier = outlier_score >= 3.0
\`\`\`

Videos 3+ standard deviations above the median are flagged as outliers. These get the "Generate idea" and "Schedule a response" buttons in the UI.

## The LinkedIn wedge

The moat isn't "we have API access" — anyone can sign up for Netrows. The moat is making LinkedIn video data *actionable*: cross-platform trend correlation, B2B-specific benchmarks, and an insight-to-publish loop that connects discovery to action.

No other tool in the market does this. Virlo doesn't track LinkedIn at all.

## Adding a new provider

1. Create \`app/platforms/newplatform.py\` implementing the ABC
2. Add to the factory with an env-var gate
3. Write tests that mock the HTTP calls
4. The rest of the codebase — search, workers, analytics — picks it up automatically

This is the power of the adapter pattern: the DataProviderRouter is insurance against any single data source changing terms, raising prices, or shutting down.`,
  },
];

export function getPost(slug: string): BlogPost | undefined {
  return BLOG_POSTS.find((p) => p.slug === slug);
}
