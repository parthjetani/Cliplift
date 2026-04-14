# Cliplift

Short-form video analytics + publishing tool. The "anti-credit" alternative to Virlo.ai.

**Positioning:** Flat-rate pricing ($29/$79/$149), LinkedIn-first analytics, insight-to-publish loop. See [`tmp/STRATEGY.md`](./tmp/STRATEGY.md) for the competitive strategy.

---

## Architecture

- **Frontend:** Next.js 15 (App Router) + Tailwind + shadcn/ui → Vercel
- **Backend:** FastAPI (Python 3.12) → Railway (auto-sleep)
- **Database:** Supabase Postgres + Supabase Auth + Supabase Storage
- **Cache / Queue:** Upstash Redis + Upstash QStash (serverless)
- **Data:** YouTube Data API + Netrows (LinkedIn) + Data365 (TikTok/Instagram)
- **Payments:** Stripe (checkout + webhooks + customer portal)
- **AI:** Anthropic Claude (content briefs)

All external integrations have **mock fallbacks** — the full stack runs end-to-end without any API keys. **299 backend tests passing.**

**Design system:** Indigo primary + Teal accent. Dark mode via `next-themes`. Custom brand logo (icon + wordmark, light/dark variants). Favicon included.

> See [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) for the full architecture doc.

---

## Quickstart

### Prerequisites
- Python 3.12+ with [`uv`](https://docs.astral.sh/uv/) installed
- Node.js 20+
- Docker (for local Redis)
- [Supabase CLI](https://supabase.com/docs/guides/cli) (`npm install -g supabase`)

### Setup
```bash
# 1. Copy environment template
cp .env.example .env

# 2. Install dependencies
make install

# 3. Start Supabase locally (Postgres + Auth)
make supabase-start
# Copy the printed SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_JWT_SECRET into .env

# 4. Start Redis
make redis-start

# 5. Apply database migrations
make migrate

# 6. Run dev servers
make dev
```

Backend: http://localhost:8000 (docs at `/docs`)
Frontend: http://localhost:3000

### Verify it works
```bash
curl http://localhost:8000/health
# → {"status":"ok","environment":"development"}
```

---

## Project Structure

```
cliplift/
├── backend/                 # FastAPI app
│   ├── app/
│   │   ├── auth/            # Profile + Supabase JWT + team management
│   │   ├── creators/        # Creator tracking (models, schemas, service, routes)
│   │   ├── videos/          # Video tracking (same shape)
│   │   ├── discovery/       # Trend search + niche management + AI briefs
│   │   ├── publishing/      # OAuth, scheduled posts, presign, publishers
│   │   ├── analytics/       # Dashboard aggregation endpoints
│   │   ├── billing/         # Stripe, plan limits, enforcement middleware
│   │   ├── ai/              # AIClient abstraction (Claude + Mock)
│   │   ├── platforms/       # DataProviderRouter + adapters
│   │   ├── workers/         # QStash-triggered HTTP endpoints
│   │   └── common/          # Cache, rate limit, encryption, pagination, errors, storage
│   ├── alembic/             # Database migrations
│   └── tests/               # 299 tests (pytest-asyncio)
│
├── frontend/                # Next.js 15 app
│   ├── app/
│   │   ├── (auth)/          # Login, register
│   │   ├── (dashboard)/     # All authenticated routes (22 pages)
│   │   └── (marketing)/     # Landing, /compare/virlo, /discover (public)
│   ├── components/          # UI components by domain
│   └── lib/                 # API client, Supabase client, types
│
├── docs/                    # 11 comprehensive documentation files
├── supabase/                # Supabase CLI config
├── docker-compose.yml       # Local Redis
├── Makefile                 # Common commands
└── .env.example
```

---

## Common Commands

| Command | Description |
|---------|-------------|
| `make install` | Install backend (uv) + frontend (npm) deps |
| `make dev` | Run both servers concurrently |
| `make backend` | Backend only (`:8000`) |
| `make frontend` | Frontend only (`:3000`) |
| `make migrate` | Apply Alembic migrations |
| `make db-reset` | Drop all tables + re-apply migrations |
| `make test` | Run backend tests |
| `make lint` | Lint backend (ruff) + frontend (eslint) |
| `make fmt` | Format backend (ruff) + frontend (prettier) |
| `make worker-publish` | Manually trigger publish-scheduled worker (dev) |

---

## Mock-First Development

Every external integration falls back to a mock when its API key is missing:

| Service | Env Var | Mock Behavior |
|---------|---------|---------------|
| YouTube Data API | `YOUTUBE_API_KEY` | `MockDataProvider` — deterministic fake videos |
| Netrows (LinkedIn) | `NETROWS_API_KEY` | `MockDataProvider` — deterministic fake LinkedIn data |
| Data365 (TikTok/IG) | `DATA365_API_KEY` | `MockDataProvider` — deterministic fake TikTok + IG data |
| Stripe | `STRIPE_SECRET_KEY` | `MockStripeClient` — deterministic checkout sessions, synthetic webhooks |
| Anthropic (AI) | `ANTHROPIC_API_KEY` | `MockAIClient` — deterministic content briefs |
| Google OAuth | `GOOGLE_OAUTH_CLIENT_ID` | `MockOAuthProvider` + `MockPublisher` for YouTube |
| Meta OAuth | `META_OAUTH_CLIENT_ID` | `MockOAuthProvider` + `MockPublisher` for Instagram |
| Supabase Storage | `STORAGE_BACKEND=auto` | `LocalStorageBackend` — writes to `./uploads/` |
| Upstash Redis | `UPSTASH_REDIS_REST_URL` | In-memory `cachetools.TTLCache` |
| QStash Workers | `QSTASH_*_SIGNING_KEY` | Accepts `X-Dev-Worker-Token` header |

When you're ready to go live, drop real keys into `.env` — no code changes needed.

> See [`docs/ENVIRONMENT.md`](./docs/ENVIRONMENT.md) for the complete env var reference.

---

## Documentation

Comprehensive internal docs in [`docs/`](./docs/):

| Doc | Description |
|-----|-------------|
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | System overview, module layout, mock-first pattern, data flow |
| [API_REFERENCE.md](./docs/API_REFERENCE.md) | All 38 endpoints with request/response schemas |
| [DATABASE_SCHEMA.md](./docs/DATABASE_SCHEMA.md) | 13 tables, columns, relationships, migrations |
| [AUTHENTICATION.md](./docs/AUTHENTICATION.md) | Supabase JWT, dependency chain, plan enforcement |
| [BILLING.md](./docs/BILLING.md) | Stripe integration, plan limits, webhook handling, trial logic |
| [PUBLISHING.md](./docs/PUBLISHING.md) | Upload flow, publisher abstraction, OAuth, worker pipeline |
| [DATA_PROVIDERS.md](./docs/DATA_PROVIDERS.md) | DataProviderRouter, mock-first, provider adapters |
| [WORKERS.md](./docs/WORKERS.md) | QStash workers, cron schedules, dev triggers |
| [TESTING.md](./docs/TESTING.md) | 299 tests, fixtures, patterns, known gotchas |
| [ENVIRONMENT.md](./docs/ENVIRONMENT.md) | Every env var, mock-fallback decision tree |
| [DEPLOYMENT.md](./docs/DEPLOYMENT.md) | Railway + Vercel + QStash + Stripe production setup |

---

## License

Proprietary — all rights reserved.
