# Todo

Active task list for Cliplift, derived from `C:\Users\parth\.claude\plans\synthetic-crafting-umbrella.md`.
Per `CLAUDE.md` → Task Management: plan here, track progress, log lessons in `tasks/lessons.md`.

---

## Status snapshot (verified 2026-04-14)

**Weeks 1–5 — COMPLETE.** 27 chunks shipped, 299 backend tests passing, frontend builds clean.
**Brand + design system** — Indigo + Teal palette, dark mode, real logo/favicon, green→teal sweep.
**Documentation** — 11 comprehensive docs in `docs/`.
**Next:** Week 6 — Deploy & Launch.

| # | Chunk | State | Tests |
|---|---|---|---|
| 1–11 | Foundation, auth, DataProviderRouter, tracking, niches, workers | ✅ done | 163 baseline |
| 12 | Analytics backend + cache helper | ✅ done | included in 163 |
| 13 | Recharts wrappers + dashboard rebuild | ✅ done | manual |
| 14 | Creator + Video + Niche detail charts | ✅ done | manual |
| 15 | AI content brief (backend + frontend) | ✅ done | included in 163 |
| 16 | Polish + browser E2E | ✅ folded into 21 | — |
| 17 | Storage + presign + ScheduledPost CRUD | ✅ done | +49 → 212 |
| 18 | Publisher abstraction (YT + IG + mock) | ✅ done | +22 → 234 |
| 19 | QStash publish-scheduled worker | ✅ done | +8 → 242 |
| 20 | Frontend post composer + CTA | ✅ done | manual (242) |
| 21 | Calendar + posts list + E2E sweep | ✅ done | +2 → 244 |
| 22 | Plan tier config + trial + MockStripe | ✅ done | +26 → 270 |
| 23 | Real Stripe wiring | ✅ done | +13 → 283 |
| 24 | Plan enforcement middleware | ✅ done | +16 → 299 |
| 25 | Settings UIs (billing, team, connections) | ✅ done | manual |
| 26 | Landing page + /compare/virlo | ✅ done | manual |
| 27 | Polish pass + Week 5 E2E sweep | ✅ done | manual |

**Backend tests: 299.** **Frontend: 22 dashboard routes, build ✓, lint ✓.**

### Key decisions (logged in memory)
- Storage backend = Supabase Storage, not R2
- Instagram Reels APPROVED by Meta (2026-04-11)
- Mock-first Stripe; default plan `"creator"` + 7-day trial (NOT `"free"`)
- Hard cancellation cutoff (`plan="cancelled"`, no cancel→trial loophole)
- Trial expiry for never-paid = also hard cutoff (computed live, no webhook needed)
- Creator tier: 1 platform connection (strongest upgrade hook)
- Brand: Indigo `#6366F1` (primary, navigation), Teal `#0D9488` (accent, outliers/publish/velocity), Red (destructive only)

---

## Week 6 — Deploy & Launch

**Plan reference:** `synthetic-crafting-umbrella.md:735-747` · **Full guide:** `docs/DEPLOYMENT.md` · `make deploy-checklist`

### Infra
- [ ] Railway: connect repo, root=`backend/`, start `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Vercel: import repo, root=`frontend/`, framework=Next.js
- [ ] Set ALL production env vars in Railway (see `docs/ENVIRONMENT.md`)
- [ ] Generate FRESH `ENCRYPTION_KEY` for production (`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`)
- [ ] Run migrations against prod DB: `DATABASE_URL=<prod> alembic upgrade head`
- [ ] Create Supabase Storage bucket: `cliplift-videos` (private)
- [ ] Domain + SSL (CORS config from Week 1 already in place)
- [ ] Sentry + basic logging

### Scheduled workers
- [ ] Configure 4 QStash cron schedules against production worker URLs (see `docs/WORKERS.md`):
  - `scrape-creators` — daily
  - `scrape-videos` — 6-hourly
  - `discover-trends` — hourly
  - `publish-scheduled` — 5-minute (120s timeout)
  - `collect-analytics` — daily

### Billing + OAuth
- [ ] Add Stripe webhook endpoint: `https://api.cliplift.com/api/v1/billing/webhook`
- [ ] Update OAuth redirect URIs to production domain (YouTube, Instagram, LinkedIn, TikTok)

### Smoke + launch
- [ ] `curl https://api.cliplift.com/health`
- [ ] Seed 10 niches with real data for demo
- [ ] Beta invite 10–20 creators
- [ ] Product Hunt launch prep
- [ ] "Virlo Alternative" SEO blog posts
- [ ] Creator partnership outreach
- [ ] Reddit / Discord community posts

---

## Chunk history

### Chunk 17 — Storage + presign + ScheduledPost CRUD — 2026-04-11
- 10 files (4 new, 6 edits) + 3 test files; +49 tests → 212, zero regressions
- Bug #1: storage factory keyed off `SUPABASE_SERVICE_ROLE_KEY` (set when local Supabase runs) → dev tests accidentally hit Supabase Storage. Replaced with `STORAGE_BACKEND` setting (`auto`/`local`/`supabase`); `auto` only picks Supabase in `ENVIRONMENT=production`. +5 factory tests.
- Bug #2: `field_validator` raising `ValueError` produced JSON-unserializable error responses (Pydantic v2 stuffs raw exception in `ctx.error`). Replaced with `Literal[...]` + `pattern` constraints — Pydantic core emits clean errors natively.

### Chunk 18 — Publisher abstraction (Mock + YT + IG) — 2026-04-11
- 9 new files in `app/publishing/publishers/` + `publisher_router.py` + 4 test files; +22 tests → 234 (green on first run)
- Extended `OAuthProvider` ABC with `refresh_access_token` — Google + Meta + Mock all implement it
- Hand-rolled YouTube `videos.insert` multipart/related via httpx — avoided `google-api-python-client` dep
- Shared `_credentials.py`: decrypt → expiry check (5-min safety margin) → refresh → encrypted persist
- `Publisher.publish` accepts both `video_bytes` (YT binary) and `video_url` (IG Reels fetches from URL)

### Chunk 19 — QStash publish-scheduled worker — 2026-04-11
- `workers/publish_scheduled.py` (new), `workers/routes.py` (edit), `Makefile` worker-publish target, `test_publish_worker.py` (8 tests) → 242
- Uses `SELECT FOR UPDATE SKIP LOCKED` for safe concurrent pickup; per-post try/except with rollback + refetch ensures failures mark `status=failed`, never stuck `publishing`
- Bug #3: `discover_trends` had `LIMIT 100` with **no ORDER BY** — >100 active niches could leave new niches unprocessed indefinitely. Fixed with `ORDER BY last_analyzed_at ASC NULLS FIRST, created_at ASC`.
- Fixture lesson: any fixture creating `AsyncSessionLocal()` outside conftest must `await engine.dispose()` in teardown (asyncpg loop isolation).

### Chunk 20 — Frontend post composer + "Schedule a response" CTA — 2026-04-11
- 7 new frontend files + 4 edits + 1 backend route addition; frontend build/lint clean
- Flow: outlier in `/discover` → "Schedule a response" → `/dashboard/posts/new?inspired_by=<id>` → drag/drop video → progress bar → submit → detail page
- Dev-only local upload sink (`PUT/GET /uploads/local/{file_key:path}`) gated by `isinstance(storage, LocalStorageBackend)` — no-op in prod, `include_in_schema=False`
- `XMLHttpRequest`-based `uploadFileWithProgress` in `lib/api.ts` (fetch has no upload-progress events)

### Chunk 21 — Calendar + posts list + E2E sweep — 2026-04-11
- 7 new files: `post-status-badge`, `post-list-row`, `content-calendar`, `posts/page`, `posts/[id]`, `calendar/page`, nav repoint. Build/lint clean.
- +2 backend tests → 244 (for the factory gating in Bug #6 below)
- **Browser E2E via Chrome MCP surfaced 3 real bugs, all fixed live:**
  1. `content-brief-dialog.tsx` auto-fetch on `onOpenChange` — Radix only fires that for its own state transitions, not controlled-prop changes. Switched to `useEffect` keyed on `open`.
  2. Calendar page passed `limit=200` but backend `PaginationParams` enforces `le=100`. Switched to cursor pagination (5×100).
  3. Publisher factory always registered real `YouTubeShortsPublisher` even with mock OAuth → 401. Added `isinstance(oauth_provider, MockOAuthProvider)` gating for YT + IG; mock OAuth → MockPublisher. +4 factory tests.
- GIF exported: `cliplift-week3-week4-e2e.gif`

### Chunk 22 — Plan tier config + trial + MockStripe — 2026-04-13
- Migration `0002_team_stripe_customer_id_and_trial`: adds `trial_ends_at`, backfills existing teams with `now() + 7 days`
- `app/billing/{plans,base,mock,factory}.py` + `PLAN_LIMITS` dict (creator/team/agency) as single source of truth
- `MockStripeClient` with deterministic checkout sessions + synthetic webhook firing; factory picks mock when `STRIPE_SECRET_KEY` empty
- `TeamResponse` extended with `plan`, `trial_ends_at`, `is_trial_active` (computed)
- +26 tests → 270

### Chunk 23 — Real Stripe wiring — 2026-04-13
- `app/billing/{real,schemas,service,routes}.py` — checkout session, customer portal, webhook handler
- `RealStripeClient` wraps `stripe.checkout.Session`, `stripe.billing_portal.Session`, `stripe.customers.create`, `stripe.Webhook.construct_event`; factory flips to real when `STRIPE_SECRET_KEY` set
- Webhook dispatch: `checkout.session.completed` → sets plan + clears trial; `subscription.updated` → plan only; `subscription.deleted` → **HARD CUTOFF** (`plan="cancelled"`, `trial_ends_at=None`, no reissue). Reactivation = fresh checkout.
- +13 tests → 283

### Chunk 24 — Plan enforcement middleware — 2026-04-13
- `app/billing/enforcement.py`: `PlanLimitExceeded(402)` envelope with `limit_name`/`current_plan`/`suggested_plan`; `require_active_plan` dependency checks cancelled + trial-expired (when `stripe_customer_id IS NULL`); per-resource gates (`enforce_creator_tracking_limit`, `enforce_platform_connection_limit`, `enforce_scheduling_enabled`)
- Wired into creators/track, niches CUD, publishing CUD, presign, connections/authorize, generate-idea
- GET endpoints keep using `get_current_team` — cancelled users can still read their data and export
- `DELETE /connections/{id}` bypasses `require_active_plan` so cancelled users can clean up
- Per-plan AI brief rate limits: creator 10/h, team 50/h, agency unlimited
- +16 tests → 299

### Chunk 25 — Settings UIs (billing + team + connections) — 2026-04-13
- `app/(dashboard)/dashboard/settings/{layout,billing,team}/page.tsx` + `components/billing/{plan-card,usage-meter,trial-banner,trial-banner-wrapper}.tsx` + `components/marketing/pricing-table.tsx` (reused on landing)
- Connections page gates "Connect" button on `max_platforms` cap; 402s surface as toasts with upgrade CTA
- Trial banner shown when `is_trial_active && days_remaining < 4`

### Chunk 26 — Landing page + /compare/virlo — 2026-04-13
- `app/page.tsx` rewritten: hero, feature grid, pricing table, footer (was just a redirect)
- `app/compare/virlo/page.tsx`: flat-rate vs credit pricing comparison, per-feature table, SEO meta
- Shared marketing components: `pricing-table`, `feature-grid`, `footer` in `components/marketing/`
- OG defaults in root layout

### Chunk 27 — Polish pass + Week 5 E2E — 2026-04-13
- Sonner toast renderer mounted in root layout; `apiAuth` wraps 402/429/500 as toasts with upgrade CTAs
- Loading-state + empty-state sweep across every dashboard route
- Error boundary on dashboard layout
- **Week 5 E2E sweep passed, 0 bugs:** sign-up → trial banner → 3 creators → 4th blocked with toast → upgrade CTA → mock checkout → synthetic webhook → plan flips → 4th creator succeeds → landing + /compare/virlo render (signed-out)

### Post-Week-5 polish — Brand + design system — 2026-04-14
- `components/brand/logo.tsx` (theme-aware SVG), `components/theme/{theme-provider,theme-toggle}.tsx` (next-themes, 3-state)
- Favicons + logo assets in `public/` (icon + wordmark, light + dark, 16/32/192/512)
- Indigo/Teal tokens in `tailwind.config.ts` + `globals.css`; theme-aware classes rolled across ~25 components
- Chart color sweep: `creators/[id]` + `niches/[id]` → `#6366F1` indigo; `videos/[id]` velocity → `#0D9488` teal
- Sidebar active state → `bg-primary/10 text-primary`; plan badge wired to `GET /teams/me` (shows real plan + trial state, "Reactivate" for cancelled, hidden on agency)
- Billing page creator count wired to `/analytics/overview.tracked_creators` (removed limit=100 hack + TODO)
- Makefile: added `worker-creators`, `worker-videos`, `worker-discover`, `worker-analytics` (share `_worker` recipe with `worker-publish`)
