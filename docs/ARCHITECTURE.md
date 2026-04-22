# Architecture

> Cliplift backend: FastAPI + async SQLAlchemy + Supabase Auth. Mock-first on every external integration.

## Stack

| Layer | Technology | Why |
|---|---|---|
| Web framework | FastAPI (Python 3.12) | Async, typed, auto-generated OpenAPI |
| ORM | SQLAlchemy 2.0 (async) | `asyncpg` driver, `expire_on_commit=False` |
| Database | PostgreSQL (Supabase-hosted) | Free tier, Auth built in |
| Auth | Supabase Auth (JWT) | No custom register/login — frontend uses Supabase JS SDK directly |
| Cache | Upstash Redis REST API | In-memory `TTLCache` fallback when `UPSTASH_REDIS_REST_URL` is empty |
| Background jobs | Upstash QStash | HTTP-triggered workers, not long-running processes |
| File storage | Supabase Storage (prod) / local disk (dev) | Presigned URLs, browser uploads directly |
| Payments | Stripe (checkout + webhooks) | Mock client when `STRIPE_SECRET_KEY` is empty |
| AI | Anthropic Claude | Mock client when `ANTHROPIC_API_KEY` is empty |
| Theming | next-themes (class strategy) | System/light/dark toggle, CSS variable swap |
| Design system | Indigo #6366F1 + Teal #0D9488 | Brand palette in `globals.css` + `tailwind.config.ts` |
| Email | Resend | Not yet wired (Week 6) |
| Monitoring | Sentry | Not yet wired (Week 6) |

## Project structure

```
backend/
  app/
    __init__.py          # __version__
    main.py              # FastAPI app factory, lifespan, router registration
    config.py            # Pydantic Settings (env vars)
    database.py          # Async engine, session factory, Base
    dependencies.py      # PaginationParams, shared deps
    auth/                # Supabase JWT validation, Profile/Team CRUD
    creators/            # Creator tracking (models, schemas, service, routes)
    videos/              # Video tracking (same shape)
    discovery/           # Public search + niche management + AI briefs
    analytics/           # Dashboard aggregation endpoints
    publishing/          # OAuth, scheduled posts, presign, publishers
    billing/             # Stripe, plan limits, enforcement middleware
    workers/             # QStash-triggered HTTP endpoints
    ai/                  # AIClient abstraction (Claude + Mock)
    platforms/           # DataProviderRouter (YouTube, Netrows, Data365, Mock)
    common/              # Cache, rate limit, encryption, pagination, errors, storage
  alembic/               # Migrations
  tests/                 # pytest-asyncio test suite
frontend/
  app/                   # Next.js 15 App Router
    (auth)/              # Login, register
    (dashboard)/         # All authenticated routes
    (marketing)/         # Landing page, /compare/virlo, /discover, /blog (public)
  components/            # React components by domain
    brand/               # Logo component (theme-aware SVG)
    theme/               # ThemeProvider + ThemeToggle (next-themes)
  lib/                   # API client, Supabase client, types, utils
  public/                # favicon, robots.txt, logo/ (SVGs + PNGs)
```

## Module pattern

Every domain module (`creators/`, `videos/`, `discovery/`, `publishing/`, `analytics/`, `billing/`) follows the same shape:

```
domain/
  __init__.py
  models.py     # SQLAlchemy ORM models
  schemas.py    # Pydantic request/response schemas
  service.py    # Business logic (DB queries, validation)
  routes.py     # FastAPI router (thin — calls service functions)
```

Routes call services. Services own DB queries. Models define the schema. Schemas define the wire format.

## Mock-first architecture

**Every external integration must work without an API key.** This is the single most important architectural decision in the codebase.

```
DataProviderRouter (registry)
  if YOUTUBE_API_KEY    -> YouTubeProvider      else MockProvider("youtube")
  if NETROWS_API_KEY    -> NetrowsProvider      else MockProvider("linkedin")
  if DATA365_API_KEY    -> Data365Provider      else MockProvider("tiktok"/"instagram")

AIClient
  if ANTHROPIC_API_KEY  -> ClaudeAIClient       else MockAIClient

StorageBackend
  if ENVIRONMENT=prod   -> SupabaseStorage      else LocalStorageBackend(./uploads)

StripeClient
  if STRIPE_SECRET_KEY  -> RealStripeClient      else MockStripeClient

PublisherRouter
  if real OAuth creds   -> YouTubeShortsPublisher else MockPublisher
  if real OAuth creds   -> InstagramReelsPublisher else MockPublisher

OAuthProvider
  if GOOGLE_OAUTH_*     -> YouTubeOAuthProvider  else MockOAuthProvider
  if META_OAUTH_*       -> InstagramOAuthProvider else MockOAuthProvider
```

Pattern implementation: each integration has a **Protocol/ABC** (`base.py`), a **real implementation**, a **mock implementation**, and a **factory function** that picks based on env vars. The factory runs once in `main.py` lifespan and stashes the result on `app.state`.

## Lifespan initialization

`app/main.py:lifespan()` builds all singletons at startup:

```python
app.state.data_provider_router = build_data_router(settings)
app.state.ai_client = get_ai_client(settings)
app.state.storage = build_storage(settings)
app.state.publisher_router = build_publisher_router(settings)
app.state.stripe_client = build_stripe_client(settings)
```

Routes pull these from `app.state` via FastAPI `Depends()` helpers:

```python
def get_storage(request: Request) -> StorageBackend:
    return request.app.state.storage
```

## Request flow

```
Browser
  -> Next.js (Vercel) [SSR or client-side]
    -> Supabase Auth SDK (login/signup)
    -> fetch("http://api.cliplift.com/api/v1/...")
      -> FastAPI middleware (CORS)
        -> Route handler
          -> Depends(get_current_user)     # JWT validation
          -> Depends(get_current_team)     # Profile + Team resolution
          -> Depends(require_active_plan)  # Plan enforcement (write endpoints)
          -> Service function (DB queries)
        <- JSON response (standard error envelope on failure)
```

## Error envelope

Every error response follows the same shape:

```json
{
  "error": {
    "code": "not_found",
    "message": "Niche not found",
    "details": null
  }
}
```

402 errors include plan upgrade metadata in `details`:

```json
{
  "error": {
    "code": "plan_limit_exceeded",
    "message": "Creator plan allows 3 tracked creators. Upgrade to Team for 25.",
    "details": {
      "limit_name": "tracked_creators",
      "current_plan": "creator",
      "suggested_plan": "team"
    }
  }
}
```

## Data flow: insight -> publish -> measure

```
1. /discover/search (PUBLIC)
   -> DataProviderRouter.search_videos(query, platforms)
   -> Z-score outlier detection
   -> Return scored results

2. /discover/generate-idea (AUTH)
   -> AIClient.generate_content_brief(video)
   -> Cached 7 days per video_id

3. /publishing/uploads/presign -> browser PUT to storage
   /publishing/scheduled-posts -> create post row

4. QStash POST /workers/publish-scheduled (5-min cron)
   -> SELECT FOR UPDATE SKIP LOCKED
   -> storage.download_bytes(file_key)
   -> publisher.publish(connection, post, bytes, url)
   -> status = published | failed

5. /analytics/* -> cached aggregation queries
```

## Key design decisions

| Decision | Rationale |
|---|---|
| Mock-first everywhere | Full stack runs with `.env` blank. Tests never hit real APIs. |
| DataProviderRouter over scrapers | Buy data until $5K MRR, swap in scrapers via the same adapter interface |
| Cursor pagination, not offset | Stable under concurrent inserts/deletes. Uses `(created_at, id)` keyset. |
| QStash workers, not background processes | Render/Railway auto-sleep compatibility. No persistent worker processes needed; any PaaS that can handle HTTP requests will do. |
| Async SQLAlchemy throughout | No sync sessions anywhere. `expire_on_commit=False` on all sessions. |
| Plan enforcement in route layer | `require_active_plan` dependency, not middleware. GET endpoints bypass it. |
| Hard cancellation cutoff | `team.plan = "cancelled"` blocks writes, reads stay open. No cancel-trial loophole. |
| `PLAN_LIMITS` as code dict | Not a DB table. Tiers change rarely; changes need code review. |
| OAuth tokens encrypted at rest | Fernet AES-256. DB never sees plaintext. |
| `SELECT FOR UPDATE SKIP LOCKED` for worker | Safe concurrent pickup. Status flips to `publishing` in the same transaction. |
