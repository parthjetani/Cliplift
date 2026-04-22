# Environment Variables

> All external service keys are optional. Missing keys trigger mock fallbacks. The full stack runs with `.env` blank.

## Quick start

```bash
cp .env.example .env
npx supabase start          # Fills Supabase vars automatically
make dev                     # Backend :8000, frontend :3000
```

## Variable reference

### Application

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | no | `development` | `development` / `staging` / `production`. Controls storage backend selection, log format. |
| `LOG_LEVEL` | no | `INFO` | Python logging level. |
| `APP_NAME` | no | `Cliplift` | Shown in health check + OpenAPI docs. |
| `API_V1_PREFIX` | no | `/api/v1` | Route prefix for all API routers. |
| `FRONTEND_URL` | no | `http://localhost:3000` | Used for OAuth redirect URLs and Stripe success/cancel URLs. **Must be the public Next.js URL, not the API host.** |

### Backend server

| Variable | Required | Default | Description |
|---|---|---|---|
| `BACKEND_HOST` | no | `0.0.0.0` | Uvicorn bind host. |
| `BACKEND_PORT` | no | `8000` | Uvicorn bind port. |
| `CORS_ORIGINS` | no | `http://localhost:3000` | Comma-separated allowed origins. |

### Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | **yes** | `postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres` | Must use `asyncpg` driver. Local Supabase runs on port 54322. |

**Production notes:**

- Use Supabase's **Transaction pooler** (`aws-0-<region>.pooler.supabase.com:6543`), NOT the direct URL (`db.<project>.supabase.co:5432` — that's IPv6-only, fails on Render/Railway/Fly free tiers which lack IPv6 outbound).
- Pooler username format is `postgres.<PROJECT_REF>`, not plain `postgres`.
- SSL param is `ssl=require`, NOT `sslmode=require` (that's psycopg2 syntax; asyncpg rejects it with a `TypeError`).
- Full production URL shape: `postgresql+asyncpg://postgres.<PROJECT_REF>:<PW>@aws-0-<REGION>.pooler.supabase.com:6543/postgres?ssl=require`
- The engine in `backend/app/database.py` sets `statement_cache_size=0` + `prepared_statement_cache_size=0` because the Transaction pooler rotates backend connections mid-session and asyncpg's prepared-statement cache becomes invalid. Don't remove these.

### Supabase Auth

| Variable | Required | Default | Description |
|---|---|---|---|
| `SUPABASE_URL` | **yes** | `http://127.0.0.1:54321` | Supabase API base URL. |
| `SUPABASE_ANON_KEY` | **yes** | empty | Publishable key from `npx supabase status`. |
| `SUPABASE_SERVICE_ROLE_KEY` | no | empty | Admin key. Used for storage (when `STORAGE_BACKEND=supabase`). |
| `SUPABASE_JWT_SECRET` | **yes** | `super-secret-jwt-...` | JWT signing secret. Default matches local Supabase CLI. |

### Upstash (Redis + QStash)

| Variable | Required | Mock fallback | Description |
|---|---|---|---|
| `UPSTASH_REDIS_REST_URL` | no | In-memory `TTLCache` | Cache + rate limit backend. |
| `UPSTASH_REDIS_REST_TOKEN` | no | (same) | |
| `QSTASH_TOKEN` | no | n/a | For sending scheduled messages (not used yet). |
| `QSTASH_CURRENT_SIGNING_KEY` | no | Dev token auth | Worker signature verification. When empty, workers accept `X-Dev-Worker-Token` header instead. |
| `QSTASH_NEXT_SIGNING_KEY` | no | (same) | Key rotation support — tries both keys. |

### Data providers

| Variable | Required | Mock fallback | Description |
|---|---|---|---|
| `YOUTUBE_API_KEY` | no | `MockDataProvider("youtube")` | YouTube Data API v3. Free, 10K quota/day. |
| `NETROWS_API_KEY` | no | `MockDataProvider("linkedin")` | Netrows LinkedIn API. ~$53/mo. |
| `DATA365_API_KEY` | no | `MockDataProvider("tiktok"/"instagram")` | Data365 TikTok + Instagram. $99/mo. |

### Stripe

| Variable | Required | Mock fallback | Description |
|---|---|---|---|
| `STRIPE_SECRET_KEY` | no | `MockStripeClient` | When set → `RealStripeClient`. |
| `STRIPE_WEBHOOK_SECRET` | no | Mock accepts `mock-signature` header | Webhook signature verification. |
| `STRIPE_PRICE_CREATOR` | no | Mock ignores | Stripe Price ID for Creator plan ($29). |
| `STRIPE_PRICE_TEAM` | no | Mock ignores | Stripe Price ID for Team plan ($79). |
| `STRIPE_PRICE_AGENCY` | no | Mock ignores | Stripe Price ID for Agency plan ($149). |

### Storage

| Variable | Required | Default | Description |
|---|---|---|---|
| `STORAGE_BACKEND` | no | `auto` | `auto` / `local` / `supabase`. `auto` = Supabase in production, local disk otherwise. |
| `SUPABASE_STORAGE_BUCKET` | no | `cliplift-videos` | Supabase Storage bucket name. |
| `LOCAL_STORAGE_DIR` | no | `./uploads` | Local disk path for dev uploads. |
| `LOCAL_STORAGE_PUBLIC_BASE_URL` | no | `http://localhost:8000` | Base URL for local upload/download routes. |

### OAuth (Google — YouTube)

| Variable | Required | Mock fallback | Description |
|---|---|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | no | `MockOAuthProvider` + `MockPublisher` for YouTube | From Google Cloud Console. |
| `GOOGLE_OAUTH_CLIENT_SECRET` | no | (same) | |
| `OAUTH_REDIRECT_BASE_URL` | no | `http://localhost:8000/api/v1/connections` | OAuth callback base. Override in production. |

### OAuth (Meta — Instagram)

| Variable | Required | Mock fallback | Description |
|---|---|---|---|
| `META_OAUTH_CLIENT_ID` | no | `MockOAuthProvider` + `MockPublisher` for Instagram | From Meta Developer Console. |
| `META_OAUTH_CLIENT_SECRET` | no | (same) | |

### AI (Anthropic)

| Variable | Required | Mock fallback | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | no | `MockAIClient` (deterministic briefs) | Content brief generation uses Claude Haiku. |

### Email (Resend)

| Variable | Required | Mock fallback | Description |
|---|---|---|---|
| `RESEND_API_KEY` | no | Console log (not yet wired) | |
| `EMAIL_FROM` | no | `alerts@cliplift.com` | |

### Monitoring

| Variable | Required | Mock fallback | Description |
|---|---|---|---|
| `SENTRY_DSN` | no | No error reporting | Sentry SDK is in deps but not yet configured. |

### Encryption

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENCRYPTION_KEY` | **yes** | `zqZJ-oUXXSIzpY...` | 32-byte Fernet key for encrypting OAuth tokens at rest. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

## Frontend environment

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | **yes** | Same as backend `SUPABASE_URL`. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **yes** | Same as backend `SUPABASE_ANON_KEY`. |
| `NEXT_PUBLIC_API_URL` | **yes** | Backend API base URL (e.g., `http://localhost:8000`). |

## Mock-fallback decision tree

```
ENVIRONMENT=development (default)
├─ YOUTUBE_API_KEY=""       → MockDataProvider("youtube")
├─ NETROWS_API_KEY=""       → MockDataProvider("linkedin")
├─ DATA365_API_KEY=""       → MockDataProvider("tiktok") + MockDataProvider("instagram")
├─ ANTHROPIC_API_KEY=""     → MockAIClient
├─ STRIPE_SECRET_KEY=""     → MockStripeClient
├─ GOOGLE_OAUTH_CLIENT_ID="" → MockOAuthProvider + MockPublisher (YouTube)
├─ META_OAUTH_CLIENT_ID=""   → MockOAuthProvider + MockPublisher (Instagram)
├─ UPSTASH_REDIS_REST_URL="" → In-memory TTLCache (cache + rate limit)
├─ STORAGE_BACKEND=auto      → LocalStorageBackend(./uploads)
└─ QSTASH_*_SIGNING_KEY=""   → Workers accept X-Dev-Worker-Token header
```
