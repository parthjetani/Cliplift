# Deployment

> Backend: Render (free tier sleeps after 15min, Starter $7/mo always-on). Frontend: Vercel (Hobby plan free). Workers: QStash cron HTTP triggers.

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
    │  Vercel (free)     │               │   Render (free/$7/mo)   │
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

Alternative hosts: Railway, Fly.io, and Cloud Run all work — the Dockerfile is portable. Render chosen for its indefinite free tier with no time limit (Railway only gives 30 days free).

## Backend: Render

### Setup

1. **Sign up** at [render.com](https://render.com) → Continue with GitHub. No credit card required for free tier.
2. Dashboard → **New +** → **Web Service** → connect your GitHub repo.
3. Configure the service:

| Field | Value |
|---|---|
| Name | `cliplift-backend` |
| Language | **Docker** (auto-detected from `backend/Dockerfile`) |
| Branch | `main` |
| Region | Pick the same region as your Supabase project for lowest DB latency |
| Root Directory | `backend` |
| Dockerfile Path | `./Dockerfile` |
| Instance Type | **Free** (upgrade to Starter $7/mo before launch — free tier sleeps) |
| Health Check Path | `/health` |

4. Generate a public domain under **Networking → Public Networking → Generate Domain** (gives you `cliplift-backend.onrender.com` or similar).

### Port handling (important)

Render injects `$PORT` (usually 10000). The current Dockerfile hardcodes `--port 8000` in its `CMD` (exec-form `CMD` does NOT expand env vars). Two workarounds:

**Option A** (current): set `PORT=8000` as an env var on Render. Render's proxy routes external traffic → container port 8000, which matches the Dockerfile.

**Option B** (proper fix, not yet done): change the Dockerfile `CMD` to shell form so `$PORT` expands:
```dockerfile
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```
Then remove the `PORT=8000` env var. Do this before porting to Fly.io / Cloud Run.

### Environment variables

Set in Render dashboard → Environment tab. **Tier 1 (required — backend won't boot without these):**

```env
ENVIRONMENT=production
PORT=8000
DATABASE_URL=postgresql+asyncpg://postgres.<PROJECT_REF>:<PW>@aws-0-<REGION>.pooler.supabase.com:6543/postgres?ssl=require
ENCRYPTION_KEY=<generate fresh — see below>
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=<Supabase → Settings → API → JWT Secret>
```

**Tier 2 (required after frontend deploys):**

```env
CORS_ORIGINS=https://cliplift.vercel.app
FRONTEND_URL=https://cliplift.vercel.app
OAUTH_REDIRECT_BASE_URL=https://<render-subdomain>.onrender.com/api/v1/connections
```

**Tier 3 (feature toggles — add when you turn on the feature):**

```env
# Real Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_CREATOR=price_...
STRIPE_PRICE_TEAM=price_...
STRIPE_PRICE_AGENCY=price_...

# QStash workers
QSTASH_CURRENT_SIGNING_KEY=sig_...
QSTASH_NEXT_SIGNING_KEY=sig_...

# Real data providers
YOUTUBE_API_KEY=AIza...
NETROWS_API_KEY=<key>
DATA365_API_KEY=<key>

# Real AI briefs
ANTHROPIC_API_KEY=sk-ant-...

# Real OAuth
GOOGLE_OAUTH_CLIENT_ID=<from google console>
GOOGLE_OAUTH_CLIENT_SECRET=<secret>
META_OAUTH_CLIENT_ID=<from meta console>
META_OAUTH_CLIENT_SECRET=<secret>

# Real cache / rate limiting (only needed when scaling past 1 instance)
UPSTASH_REDIS_REST_URL=https://<region>.upstash.io
UPSTASH_REDIS_REST_TOKEN=AX...

# Monitoring
SENTRY_DSN=https://<key>@sentry.io/<id>
```

**Generate `ENCRYPTION_KEY`:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
If lost, all encrypted OAuth tokens become unrecoverable. Store in your password manager.

### Supabase `DATABASE_URL` — use the Transaction pooler, NOT the direct URL

Supabase exposes **three** connection strings. Only one works on Render:

| Option | Hostname | Port | IPv4? | Use for |
|---|---|---|---|---|
| Direct | `db.<project>.supabase.co` | 5432 | ❌ IPv6 only | — |
| **Transaction pooler** | `aws-0-<region>.pooler.supabase.com` | **6543** | ✅ | **Render, migrations, app runtime** |
| Session pooler | `aws-0-<region>.pooler.supabase.com` | 5432 | ✅ | Long-lived connections (not our case) |

Render's free/Starter tiers have **no IPv6 outbound**. Using the direct URL fails with `OSError: [Errno 101] Network is unreachable` on every DB-touching request, even though `/health` still returns 200 (it doesn't touch the DB).

The Transaction pooler's username format is `postgres.<PROJECT_REF>`, not plain `postgres`.

**SSL param format:** asyncpg uses `ssl=require`, NOT `sslmode=require` (that's psycopg2/libpq syntax). Wrong param → `TypeError: connect() got an unexpected keyword argument 'sslmode'`.

### asyncpg + pgbouncer statement cache (already wired)

The Transaction pooler runs pgbouncer in transaction mode, which rotates backend connections between statements. asyncpg's prepared-statement cache breaks when this happens — manifests as `InvalidSQLStatementNameError: prepared statement "__asyncpg_stmt_N__" does not exist`.

`backend/app/database.py:22-38` already passes `connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0}` to the engine. Don't remove these — local dev doesn't hit the bug (direct Postgres) but production will fail on every query without them.

### Health check noise

Render polls `/health` every 5 seconds (not tunable on free/Starter). `backend/app/main.py` installs a `_HealthCheckFilter` on `uvicorn.access` so these probes don't flood the log viewer. Real traffic is still logged.

### Free-tier sleep

Render's free tier suspends the container after 15 min of inactivity — cold starts take 30-60s. Internal health probes don't count as traffic, only external HTTPS does. Before launch:
- Upgrade to **Starter tier ($7/mo)** for always-on — required for QStash crons to fire reliably.
- Or add a periodic external warm-up ping (UptimeRobot free, hitting `/health` every 10 min).

### Custom domain

1. Render → service → Settings → Custom Domains → Add → `api.cliplift.com`
2. Add the CNAME record in Cloudflare DNS (Render shows the target)
3. Render auto-provisions SSL via Let's Encrypt

## Frontend: Vercel

### Setup

1. **Sign up** at [vercel.com](https://vercel.com) → Continue with GitHub. No credit card required for Hobby plan.
2. Dashboard → **Add New → Project** → import the Cliplift repo.
3. Configure:

| Field | Value |
|---|---|
| Project Name | `cliplift` |
| Framework Preset | Next.js (auto-detected) |
| Root Directory | `frontend` (click Edit) |
| Build Command | default (`next build`) |
| Install Command | default (`npm install`) |

### Environment variables

```env
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=https://<render-subdomain>.onrender.com
```

`NEXT_PUBLIC_*` vars are baked into the client bundle at build time — changing them requires a redeploy, not just an env update.

### `.gitignore` gotcha

The root `.gitignore` (from toptal's Python generator) contains `lib/` under "Distribution / packaging". That pattern matches by basename anywhere in the tree, including `frontend/lib/`. If this isn't explicitly un-ignored, `git push` sends an incomplete tree and Vercel's build fails with `Module not found: Can't resolve '@/lib/*'`.

Fix (already applied): the Cliplift custom section at the bottom of `.gitignore` has:
```
!frontend/lib/
!frontend/lib/**
```
If adding a new language folder like `mobile/lib/`, extend the same pattern.

### Custom domain

1. Vercel → project → Settings → Domains → `cliplift.com`
2. Add the A / CNAME records in Cloudflare
3. Vercel auto-provisions SSL

## Database: Supabase

### Production project

Create a separate project from your local dev (Supabase dashboard → New Project). Pick the region matching your Render region for lowest latency.

Get the `DATABASE_URL`: **Project Settings → Database → Connection String → Transaction pooler**. Transform for asyncpg:
- `postgresql://` → `postgresql+asyncpg://`
- `?sslmode=require` → `?ssl=require` (if present — Supabase's copy shows psycopg2 format)

### Migrations

Run from your local machine against the production DB (never edit `.env`):

**PowerShell:**
```powershell
cd backend
$env:DATABASE_URL="postgresql+asyncpg://postgres.<PROJECT_REF>:<PW>@aws-0-<REGION>.pooler.supabase.com:6543/postgres?ssl=require"
uv run alembic upgrade head
Remove-Item env:DATABASE_URL
```

**Bash:**
```bash
cd backend
DATABASE_URL="postgresql+asyncpg://postgres.<PROJECT_REF>:<PW>@aws-0-<REGION>.pooler.supabase.com:6543/postgres?ssl=require" uv run alembic upgrade head
```

Currently 3 migrations: `0001_initial`, `0002_team_stripe_customer_id_and_trial`, `0003_enable_rls_on_public_tables`.

### Row Level Security

Migration `0003` enables RLS on all 14 public tables + `alembic_version`. The backend connects as `postgres` / service_role, which bypasses RLS — transparent to the app. RLS becomes deny-by-default for PostgREST (anon + authenticated keys), which clears Supabase's Security Advisor warnings.

Any new table added in a future migration MUST enable RLS in the same migration — see the convention in `CLAUDE.md → Conventions and gotchas`.

### Storage bucket

1. Supabase dashboard → Storage → New bucket → name: `cliplift-videos` → **Private** (public access off)
2. Upload size limit: 200MB (matches frontend dropzone cap)

With `ENVIRONMENT=production` + `SUPABASE_SERVICE_ROLE_KEY` set, `STORAGE_BACKEND=auto` picks Supabase Storage automatically.

## QStash: Worker cron schedules

Requires `QSTASH_CURRENT_SIGNING_KEY` + `QSTASH_NEXT_SIGNING_KEY` set on Render, plus Render on Starter tier (free-tier sleep will cause first tick to time out).

In [Upstash QStash dashboard](https://console.upstash.com/qstash):

| Schedule | URL | Retry |
|---|---|---|
| `0 6 * * *` | `https://<your-backend>/api/v1/workers/scrape-creators` | 3 |
| `0 */6 * * *` | `https://<your-backend>/api/v1/workers/scrape-videos` | 3 |
| `0 * * * *` | `https://<your-backend>/api/v1/workers/discover-trends` | 3 |
| `*/5 * * * *` | `https://<your-backend>/api/v1/workers/publish-scheduled` | 1 |
| `0 7 * * *` | `https://<your-backend>/api/v1/workers/collect-analytics` | 3 |

Set timeout to 120s for all schedules. Signing keys are automatically injected into the request headers.

## Stripe: Webhook endpoint

1. Stripe dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://<your-backend>/api/v1/billing/webhook`
3. Events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy signing secret → set as `STRIPE_WEBHOOK_SECRET` on Render

### Stripe Price IDs

Create 3 products in Stripe:

| Product | Monthly | Env var |
|---|---|---|
| Cliplift Creator | $29/mo | `STRIPE_PRICE_CREATOR` |
| Cliplift Team | $79/mo | `STRIPE_PRICE_TEAM` |
| Cliplift Agency | $149/mo | `STRIPE_PRICE_AGENCY` |

## OAuth: Google + Meta

### Google (YouTube)

1. Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID
2. Application type: Web application
3. Authorized redirect URI: `https://<your-backend>/api/v1/connections/youtube/callback`
4. Copy Client ID + Secret → `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`
5. Enable YouTube Data API v3 in the API library

### Meta (Instagram)

1. Meta Developer Console → App → Settings → Basic
2. Valid OAuth Redirect URI: `https://<your-backend>/api/v1/connections/instagram/callback`
3. Copy App ID + Secret → `META_OAUTH_CLIENT_ID` / `META_OAUTH_CLIENT_SECRET`
4. App must be in Live mode (approved via Meta app review — Cliplift received approval 2026-04-11)

## Email: Resend (optional, pre-beta)

Resend covers both Supabase auth emails (signup confirmation, password reset) and app-level transactional email. Same account serves both via separate integration points.

1. Sign up at [resend.com](https://resend.com) (free tier: 3k/mo, 100/day, 1 domain)
2. Verify sending domain via DNS (SPF + MX + DKIM)
3. Supabase dashboard → Authentication → SMTP Settings → configure:
   - Host: `smtp.resend.com`, Port: 587, Username: `resend`, Password: `<API key>`
   - Sender email: `noreply@<your-domain>`
4. Add to Render env: `RESEND_API_KEY=re_...`, `EMAIL_FROM=alerts@<your-domain>`

## Sentry

1. Create Sentry project (Python/FastAPI)
2. Copy DSN → Render env `SENTRY_DSN`
3. `sentry-sdk[fastapi]` is in `pyproject.toml` — needs initialization in `main.py` (not yet wired)

## Monitoring checklist

| What | How |
|---|---|
| API errors | Sentry (once wired) |
| Worker health | `curl https://<your-backend>/health` |
| Worker output | QStash dashboard → Logs |
| DB health | Supabase dashboard → Database → Advisors |
| Uptime | Render dashboard → Events / Logs |
| Stripe webhooks | Stripe dashboard → Developers → Webhooks → Recent events |

## Pre-launch checklist

- [ ] Render backend deployed, `/health` returns 200
- [ ] Vercel frontend deployed, landing page renders
- [ ] `DATABASE_URL` uses Transaction pooler (NOT direct URL)
- [ ] `DATABASE_URL` has `?ssl=require`, not `?sslmode=require`
- [ ] `alembic upgrade head` run against production (all 3 migrations)
- [ ] RLS enabled on all public tables (verify in Supabase Security Advisor)
- [ ] `cliplift-videos` storage bucket created, set to private
- [ ] `ENCRYPTION_KEY` is a fresh production key (NOT the dev default)
- [ ] `CORS_ORIGINS` + `FRONTEND_URL` point at Vercel URL
- [ ] Supabase Auth → URL Configuration includes Vercel URL as Site URL + Redirect URLs
- [ ] End-to-end smoke: signup → email confirm → /dashboard loads → creators API returns 200
- [ ] Upgrade Render to Starter tier ($7/mo) before enabling QStash crons
- [ ] All 5 QStash cron schedules configured (if using scheduled workers)
- [ ] Stripe webhook endpoint verified (if accepting payments)
- [ ] OAuth redirect URIs updated to production (if shipping publishing)
- [ ] Custom domain configured with SSL
- [ ] Seed 10 niches with real keywords for demo experience
