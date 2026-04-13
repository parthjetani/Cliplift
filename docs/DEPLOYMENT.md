# Deployment

> Backend: Railway (auto-sleep, ~$5/mo). Frontend: Vercel (free tier). Workers: QStash cron HTTP triggers.

## Architecture overview

```
                         ┌─────────────────┐
                         │   Cloudflare     │
                         │   (Domain + SSL) │
                         └────────┬────────┘
                                  │
              ┌───────────────────┴──────────────────┐
              │                                       │
    ┌─────────▼─────────┐               ┌────────────▼────────────┐
    │  Vercel (free)     │               │   Railway (~$5/mo)      │
    │  Next.js frontend  │──── fetch ───>│   FastAPI backend       │
    │  cliplift.com      │               │   api.cliplift.com      │
    └────────────────────┘               └──────────┬──────────────┘
                                                    │
              ┌─────────────────────────────────────┤
              │                    │                 │                │
    ┌─────────▼──────┐  ┌────────▼────────┐  ┌────▼──────┐  ┌─────▼──────┐
    │ Supabase       │  │ Upstash Redis   │  │  QStash   │  │   Stripe   │
    │ Postgres+Auth  │  │ Cache+RateLimit │  │  Workers  │  │  Billing   │
    │ +Storage       │  │                 │  │           │  │            │
    └────────────────┘  └─────────────────┘  └───────────┘  └────────────┘
```

## Backend: Railway

### Setup

1. Create a new Railway project
2. Connect your GitHub repo (or use `railway up` CLI)
3. Set the root directory to `backend/`
4. Railway auto-detects Python + `pyproject.toml`

### Build command

```
pip install uv && uv sync --frozen
```

### Start command

```
uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway injects `$PORT`. Don't hardcode 8000.

### Environment variables

Set all production env vars in Railway's dashboard. Critical ones:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://<supabase-connection-string>
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=<from supabase dashboard>
SUPABASE_STORAGE_BUCKET=cliplift-videos
STORAGE_BACKEND=auto

STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_CREATOR=price_...
STRIPE_PRICE_TEAM=price_...
STRIPE_PRICE_AGENCY=price_...

GOOGLE_OAUTH_CLIENT_ID=<from google console>
GOOGLE_OAUTH_CLIENT_SECRET=<secret>
META_OAUTH_CLIENT_ID=<from meta console>
META_OAUTH_CLIENT_SECRET=<secret>
OAUTH_REDIRECT_BASE_URL=https://api.cliplift.com/api/v1/connections
FRONTEND_URL=https://cliplift.com

YOUTUBE_API_KEY=AIza...
NETROWS_API_KEY=<key>
DATA365_API_KEY=<key>

UPSTASH_REDIS_REST_URL=https://<region>.upstash.io
UPSTASH_REDIS_REST_TOKEN=AX...
QSTASH_CURRENT_SIGNING_KEY=sig_...
QSTASH_NEXT_SIGNING_KEY=sig_...

ANTHROPIC_API_KEY=sk-ant-...
ENCRYPTION_KEY=<generate new for production>

CORS_ORIGINS=https://cliplift.com,https://www.cliplift.com
SENTRY_DSN=https://<key>@sentry.io/<id>
```

### Auto-sleep

Railway auto-sleeps after inactivity. QStash pings `/health` before triggering workers to wake the server first. Configure a 1-minute warmup ping in QStash or use Railway's "Always On" option if budget allows.

### Custom domain

1. Railway → project settings → Custom domain → `api.cliplift.com`
2. Add the CNAME record in Cloudflare DNS
3. Railway auto-provisions SSL

## Frontend: Vercel

### Setup

1. Import the repo in Vercel
2. Set root directory to `frontend/`
3. Framework preset: Next.js (auto-detected)

### Environment variables

```env
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=https://api.cliplift.com
```

### Custom domain

1. Vercel → project settings → Domains → `cliplift.com`
2. Add the A / CNAME records in Cloudflare
3. Vercel auto-provisions SSL

## Database: Supabase

### Production Postgres

Use the Supabase dashboard to get the connection string:
- Settings → Database → Connection string → URI (use the `pooler` mode for serverless)
- Append `?sslmode=require` for Railway

### Migrations

Run against production from your local machine:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://<prod-connection-string>" uv run alembic upgrade head
```

Or create a Railway one-off command.

### Storage bucket

1. Supabase dashboard → Storage → Create bucket `cliplift-videos`
2. Set bucket to private (presigned URLs handle access)
3. Upload size limit: 200MB (matches the frontend dropzone cap)

## QStash: Worker cron schedules

In the [Upstash QStash dashboard](https://console.upstash.com/qstash):

| Schedule | URL | Retry |
|---|---|---|
| `0 6 * * *` | `https://api.cliplift.com/api/v1/workers/scrape-creators` | 3 |
| `0 */6 * * *` | `https://api.cliplift.com/api/v1/workers/scrape-videos` | 3 |
| `0 * * * *` | `https://api.cliplift.com/api/v1/workers/discover-trends` | 3 |
| `*/5 * * * *` | `https://api.cliplift.com/api/v1/workers/publish-scheduled` | 1 |
| `0 7 * * *` | `https://api.cliplift.com/api/v1/workers/collect-analytics` | 3 |

Set timeout to 120s for all schedules. The signing keys are automatically injected by QStash.

## Stripe: Webhook endpoint

1. Stripe dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://api.cliplift.com/api/v1/billing/webhook`
3. Events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy the signing secret → set as `STRIPE_WEBHOOK_SECRET`

### Stripe Price IDs

Create 3 products in Stripe:

| Product | Monthly price | Price ID → env var |
|---|---|---|
| Cliplift Creator | $29/mo | `STRIPE_PRICE_CREATOR` |
| Cliplift Team | $79/mo | `STRIPE_PRICE_TEAM` |
| Cliplift Agency | $149/mo | `STRIPE_PRICE_AGENCY` |

For annual billing: create additional annual prices (30% discount) and map them in the checkout service (Chunk 23 currently only uses monthly — annual support is a code change in `billing/service.py`).

## OAuth: Google + Meta

### Google (YouTube)

1. Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID
2. Application type: Web application
3. Authorized redirect URI: `https://api.cliplift.com/api/v1/connections/youtube/callback`
4. Copy Client ID + Secret → `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`
5. Enable YouTube Data API v3 in the API library

### Meta (Instagram)

1. Meta Developer Console → App → Settings → Basic
2. Valid OAuth Redirect URI: `https://api.cliplift.com/api/v1/connections/instagram/callback`
3. Copy App ID + Secret → `META_OAUTH_CLIENT_ID` / `META_OAUTH_CLIENT_SECRET`
4. App must be in Live mode (approved via Meta app review)

## Sentry

1. Create a Sentry project (Python/FastAPI)
2. Copy the DSN → `SENTRY_DSN`
3. `sentry-sdk[fastapi]` is already in `pyproject.toml` — just needs initialization in `main.py` (not yet wired)

## Monitoring checklist

| What | How |
|---|---|
| API errors | Sentry (once wired) |
| Worker health | Check `/health` endpoint returns `{"status": "ok"}` |
| Worker output | QStash dashboard → Logs (shows response bodies) |
| DB health | Supabase dashboard → Database → Health |
| Uptime | Railway dashboard → Deployments → Logs |
| Stripe webhooks | Stripe dashboard → Developers → Webhooks → Recent events |

## Pre-launch checklist

- [ ] Railway backend deployed + health check passes
- [ ] Vercel frontend deployed + landing page renders
- [ ] `DATABASE_URL` points at production Supabase
- [ ] Run `alembic upgrade head` against production
- [ ] Create `cliplift-videos` storage bucket in Supabase
- [ ] All 4 QStash cron schedules configured
- [ ] Stripe webhook endpoint verified (send test event)
- [ ] Google + Meta OAuth redirect URIs updated to production
- [ ] CORS_ORIGINS includes the production domain
- [ ] `ENCRYPTION_KEY` is a fresh production key (not the dev default)
- [ ] `FRONTEND_URL` and `OAUTH_REDIRECT_BASE_URL` point at production
- [ ] Seed 10 niches with real keywords for the demo experience
- [ ] Verify: sign up → track creator → create niche → worker runs → dashboard populates
