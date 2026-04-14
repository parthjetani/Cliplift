# Todo

Active task list for Cliplift, derived from `C:\Users\parth\.claude\plans\synthetic-crafting-umbrella.md`.
Per `CLAUDE.md` → Task Management: plan here, verify with user, track, then add a Review section.

---

## Status snapshot (verified 2026-04-13)

**Week 3 — Analytics & AI Brief** — ✅ Complete (5/5 chunks).
**Week 4 — Publishing & Scheduling** — ✅ Complete (5/5 chunks). E2E sweep passed, 3 bugs found + fixed.
**Week 5 — Billing, Polish & Landing** — ✅ Complete (6/6 chunks). E2E sweep passed, 0 bugs.
**Brand + Design System** — ✅ Indigo + Teal palette, dark mode, real logo/favicon, green→teal sweep.
**Documentation** — ✅ 11 comprehensive docs in `docs/`.

| # | Chunk | State | Tests |
|---|---|---|---|
| 12 | Analytics backend + cache helper | ✅ done | included in 163 |
| 13 | Recharts wrappers + dashboard rebuild | ✅ done | manual |
| 14 | Creator + Video + Niche detail charts | ✅ done | manual |
| 15 | AI content brief (backend + frontend) | ✅ done | included in 163 |
| 16 | Polish + browser E2E test pass | ✅ folded into 21 | — |
| **17** | **Storage + presign + ScheduledPost CRUD** | **✅ done** | **+49 → 212** |
| **18** | **Publisher abstraction (YT + IG + mock)** | **✅ done** | **+22 → 234** |
| **19** | **QStash publish-scheduled worker** | **✅ done** | **+8 → 242** |
| **20** | **Frontend post composer + CTA** | **✅ done** | **manual (242)** |
| **21** | **Calendar + posts list + E2E sweep** | **✅ done** | **+2 → 244** |
| **22** | **Plan tier config + trial + MockStripe** | **✅ done** | **+26 → 270** |
| **23** | **Real Stripe wiring** | **✅ done** | **+13 → 283** |
| **24** | **Plan enforcement middleware** | **✅ done** | **+16 → 299** |
| **25** | **Settings UIs (billing, team, connections)** | **✅ done** | **manual** |
| **26** | **Landing page + /compare/virlo** | **✅ done** | **manual** |
| **27** | **Polish pass + Week 5 E2E sweep** | **✅ done** | **manual** |

**Current backend test count: 299**
**Frontend: 22 dashboard routes, build ✓, lint ✓**

**Key decisions (logged in memory):**
- Storage backend = Supabase Storage, not R2
- Instagram Reels APPROVED by Meta (2026-04-11)
- Mock-first Stripe; default plan "creator" + 7-day trial (NOT "free")
- Hard cancellation cutoff (`plan="cancelled"`, no cancel→trial loophole)
- Trial expiry for never-paid = also hard cutoff (computed live, no webhook needed)
- Creator tier: 1 platform connection (strongest upgrade hook)

**Next: Week 6 — Deploy & Launch** (see `docs/DEPLOYMENT.md` for the full checklist)

---

## ✅ Chunk 17 — Storage Adapter + Presign + Scheduled Post CRUD — DONE (2026-04-11)

**Result:** 212 / 212 backend tests passing (+49 over the 163 baseline, zero regressions).

**Plan reference:** `synthetic-crafting-umbrella.md` §17 → Chunk 17

### Pre-flight
- [x] Re-read `app/publishing/models.py` — model already exists, only `file_key` comment needs updating
- [x] Verify `0001_initial.py` already creates `scheduled_posts` and `post_analytics` tables
- [x] Skim `app/common/cache.py` and `app/common/ratelimit.py` for the mock-first fail-open pattern
- [x] Skim `app/platforms/factory.py` for the env-based factory pattern

### Backend implementation
- [x] Create `backend/app/common/storage.py` — `StorageBackend` Protocol + `LocalStorageBackend` + `SupabaseStorageBackend` + `build_storage()` factory
- [x] Edit `backend/app/publishing/models.py` — `file_key` comment "Cloudflare R2 object key" → "Supabase Storage object key"
- [x] Create `backend/app/publishing/schemas.py` — `PostStatus`, `PresignRequest/Response`, `ScheduledPostCreate/Update/Response`
- [x] Create `backend/app/publishing/service.py` — presign + CRUD with status guards + ownership checks + best-effort file delete
- [x] Create `backend/app/publishing/routes.py` — 6 endpoints under `/api/v1/publishing/`
- [x] Edit `backend/app/main.py` — `app.state.storage = build_storage(settings)` in lifespan, register `publishing_router`, swap R2 → Supabase Storage in startup log
- [x] Edit `backend/app/config.py` — remove R2 settings, add `STORAGE_BACKEND` (`auto`/`local`/`supabase`) + `SUPABASE_STORAGE_BUCKET` + `LOCAL_STORAGE_DIR` + `LOCAL_STORAGE_PUBLIC_BASE_URL`

### Tests
- [x] `backend/tests/test_storage.py` — 18 tests (LocalStorage round-trip + SupabaseStorage mocked + factory matrix)
- [x] `backend/tests/test_publishing_presign.py` — 9 tests (auth, validation, success path)
- [x] `backend/tests/test_scheduled_posts.py` — 22 tests (auth, CRUD, status guards, cross-team isolation)

### Verification
- [x] `pytest tests/test_storage.py tests/test_publishing_presign.py tests/test_scheduled_posts.py -v` — 45 / 45 green
- [x] `pytest` — 212 / 212 total, no regressions
- [x] Two latent bugs caught and fixed mid-chunk:
  - `STORAGE_BACKEND` setting added so local Supabase doesn't accidentally activate Supabase Storage in dev
  - Validators use `Literal` + `pattern` instead of `field_validator` to produce JSON-safe errors

---

## ✅ Chunk 18 — Publisher Abstraction (Mock + Real YouTube + Real Instagram) — DONE (2026-04-11)

**Result:** 234 / 234 backend tests passing (+22 over Chunk 17, zero regressions). Decision delta: hand-rolled YouTube multipart upload via httpx (no `google-api-python-client` dep), and extended the OAuth ABC with `refresh_access_token` rather than putting refresh logic inside each publisher.

**Plan reference:** `synthetic-crafting-umbrella.md` §17 → Chunk 18

### Pre-flight
- [x] Re-read `app/platforms/{base,router,factory}.py` to mirror the abstraction shape exactly
- [x] Re-read `app/publishing/oauth_providers/{youtube,instagram}.py` to understand token refresh flow
- [x] Re-read `app/common/encryption.py` — `decrypt_token` / `encrypt_token` for OAuth tokens at rest
- [x] **Decision:** skip `google-api-python-client` dep — hand-roll multipart/related via httpx (no new dep, smaller mock surface, mirrors every other adapter)
- [x] Confirm `httpx` covers the Meta Graph API calls (yes — already in deps)

### OAuth ABC extension (cross-cutting prerequisite)
- [x] Add `refresh_access_token(refresh_token: str) -> TokenExchangeResult` to `OAuthProvider` ABC
- [x] Implement on `YouTubeOAuthProvider` — Google `grant_type=refresh_token` flow
- [x] Implement on `InstagramOAuthProvider` — Meta `grant_type=fb_exchange_token` long-lived refresh
- [x] Implement on `MockOAuthProvider` — deterministic, encodes input refresh token in output for assertion

### Backend implementation
- [x] Create `backend/app/publishing/publishers/__init__.py`
- [x] Create `backend/app/publishing/publishers/base.py` — `PublishResult`, `PublisherError`, `Publisher` ABC. Signature accepts both `video_bytes` (binary uploaders) and `video_url` (URL-fetch APIs like Instagram Reels), plus `db` so publishers can persist refreshed tokens
- [x] Create `backend/app/publishing/publishers/_credentials.py` — shared `get_fresh_access_token()` helper used by both real publishers (decrypt → check expiry with 5-min safety margin → refresh → persist encrypted)
- [x] Create `backend/app/publishing/publishers/mock.py` — `MockPublisher` with deterministic `mock_<id>` post IDs
- [x] Create `backend/app/publishing/publishers/youtube.py` — `YouTubeShortsPublisher`, hand-rolled multipart/related to `videos.insert?uploadType=multipart&part=snippet,status`, `categoryId=22` (People & Blogs), `privacyStatus=public`, returns `https://youtube.com/shorts/{id}`
- [x] Create `backend/app/publishing/publishers/instagram.py` — `InstagramReelsPublisher`, full three-step container flow: create → poll status (5s interval, 90s timeout) → publish, caption built from `title + description + hashtags`
- [x] Create `backend/app/publishing/publisher_router.py` — `PublisherRouter` class mirroring `DataProviderRouter` shape
- [x] Create `backend/app/publishing/publishers/factory.py` — `build_publisher_router(settings)` always wires real YouTube + Instagram (auth happens per-connection at publish time, not at construction), mock for LinkedIn + TikTok
- [x] Edit `backend/app/main.py` — `app.state.publisher_router = build_publisher_router(settings)` in lifespan, close on shutdown

### Tests
- [x] `backend/tests/test_publisher_mock.py` — 3 tests (valid shape, deterministic for same post id, every platform)
- [x] `backend/tests/test_publisher_youtube.py` — 7 tests (happy path, multipart body assertions, shorts URL format, expired-token refresh, fresh-token skip, 400 error, missing-id response)
- [x] `backend/tests/test_publisher_instagram.py` — 7 tests (full three-step flow, container payload assertions, polling waits for FINISHED, polling errors on ERROR state, polling timeout, missing platform_user_id, container creation 400)
- [x] `backend/tests/test_publisher_factory.py` — 5 tests (router has all platforms, YT real, IG real, LinkedIn + TikTok mock, summary completeness)

### Verification
- [x] `pytest tests/test_publisher_*.py -v` — **22 / 22 green** on first run
- [x] `pytest` — **234 / 234** total, zero regressions
- [x] All publisher tests use `unittest.mock.patch` on `httpx.AsyncClient` — same pattern as `test_storage.py::TestSupabaseStorageBackend`
- [x] Token refresh persistence verified end-to-end: test asserts `db.add` + `db.commit` called, encrypted token in DB decrypts to refreshed value, and the upload Authorization header carries the new token

---

## ✅ Chunk 19 — QStash Publish-Scheduled Worker — DONE (2026-04-11)

**Result:** 242 / 242 backend tests passing (+8, zero regressions). Plus a latent bug fix in `discover_trends` query ordering.

### Files shipped
- `app/workers/publish_scheduled.py` (NEW) — worker logic with `SELECT FOR UPDATE SKIP LOCKED` pickup + per-post try/except with rollback + refetch on failure
- `app/workers/routes.py` (edit) — registered `/workers/publish-scheduled`, added `get_storage_from_app` + `get_publisher_router_from_app` helpers
- `app/workers/discover_trends.py` (edit) — **latent bug fix:** added `ORDER BY last_analyzed_at ASC NULLS FIRST, created_at ASC` so brand-new niches always get picked before stale ones (was failing in production scenarios where >100 active niches existed)
- `Makefile` — `worker-publish` target curls the endpoint with the dev token
- `tests/test_publish_worker.py` (NEW) — 8 integration tests

### Test coverage
- Empty DB → zero summary
- Status guards (draft / publishing / future scheduled_for not picked)
- Happy path — full state transition + platform_post_id + media_url
- Publisher raises → row marked failed with error message, worker returns 200
- Storage missing file → row marked failed (rollback + refetch flow works under exception)
- **SKIP LOCKED concurrency proof** — two parallel workers with separate sessions each pick a different due post

### Two issues caught and fixed during the build
1. `db_session` fixture leaked asyncpg pool connections across test boundaries → "different loop" error. Fix: mirror conftest `client` fixture pattern and call `await engine.dispose()` in teardown.
2. `discover_trends` had `LIMIT 100` with **no ORDER BY** — accumulated test pollution surfaced this. Fixed by ordering NULLS FIRST so unprocessed niches always lead, with `created_at ASC` as tiebreaker. Real production correctness improvement.

---

## ⏳ Chunk 19 — Original task list (kept for reference)

**Plan reference:** `synthetic-crafting-umbrella.md` §17 → Chunk 19

**Goal:** HTTP endpoint that QStash hits on a 5-minute cron, picks up due posts via `SELECT FOR UPDATE SKIP LOCKED`, runs them through the publisher router, and writes status + platform_post_id back to the row.

**Test target:** +8 (228 → 236)

### Pre-flight
- [ ] Re-read `app/workers/{routes,middleware,scrape_videos}.py` for the QStash worker pattern
- [ ] Re-read `app/workers/middleware.py` — confirm `verify_qstash_signature` accepts the dev token
- [ ] Confirm Postgres `FOR UPDATE SKIP LOCKED` is supported by asyncpg (it is — standard SQL)

### Backend implementation
- [ ] Create `backend/app/workers/publish_scheduled.py`:
  - `async def publish_scheduled(db, storage, publisher_router, *, max_posts=1) -> dict`
  - Step 1: `SELECT * FROM scheduled_posts WHERE status='scheduled' AND scheduled_for <= now() ORDER BY scheduled_for ASC LIMIT N FOR UPDATE SKIP LOCKED`
  - Step 2: For each row → set `status='publishing'` → commit (releases the row lock so a peer worker doesn't double-pick)
  - Step 3: `video_bytes = await storage.download_bytes(post.file_key)`
  - Step 4: Load `PlatformConnection` (eagerly), decrypt tokens
  - Step 5: `result = await publisher_router.get(post.platform).publish(connection, post, video_bytes)`
  - Step 6: On success → `status='published'`, `platform_post_id`, `media_url`, `published_at = result.published_at`
  - Step 7: On failure → `status='failed'`, `error_message=str(exc)[:1000]`. **Do not raise** — return summary so the worker stays alive for the next post.
  - Step 8: Return `{processed, succeeded, failed, errors: [...]}`
- [ ] Edit `backend/app/workers/routes.py` — register `/workers/publish-scheduled`:
  - Decorator: `@router.post("/publish-scheduled", summary="[QStash, 5min cron, 120s timeout] Publish due scheduled posts")`
  - Pull `storage` and `publisher_router` from `app.state` via Depends
  - Query param `max_posts: int = Query(1, ge=1, le=10)`
- [ ] Edit `Makefile` — add `worker-publish` target: `curl -X POST http://localhost:8000/api/v1/workers/publish-scheduled -H "X-Dev-Worker-Token: ${ENCRYPTION_KEY}"`

### Tests
- [ ] `backend/tests/test_publish_worker.py` (~8 tests):
  - **Happy path:** create one due `scheduled` post → run worker → row is `published` with `platform_post_id` set
  - **No due posts:** empty DB → returns `{processed: 0, succeeded: 0, failed: 0}`
  - **Status guard — draft not picked:** post in `draft` status → worker ignores it
  - **Status guard — publishing not picked:** already-`publishing` post → worker ignores (avoids re-pickup on race)
  - **Future scheduled_for not picked:** `scheduled_for` in 1 hour → not picked
  - **Publisher raises:** mock publisher raises → post marked `failed` with error_message, worker returns 200 (not 500)
  - **Token refresh path:** connection with `token_expires_at < now()` → publisher refresh hook invoked → new token persisted
  - **Concurrent worker simulation:** insert 2 due posts → run two `publish_scheduled` calls in parallel → each picks a different post (proves SKIP LOCKED works)

### Verification
- [ ] `pytest tests/test_publish_worker.py -v` — all 8 green
- [ ] `pytest` — total reaches 236, no regressions
- [ ] Manual smoke: insert a `scheduled` post for `now() - 1 minute` via the API → `make worker-publish` → returns `{succeeded: 1}` → row in DB has `status='published'`
- [ ] Confirm `app/workers/routes.py` lists 4 workers (`scrape-creators`, `scrape-videos`, `discover-trends`, `publish-scheduled`)

---

## ✅ Chunk 20 — Frontend Post Composer + "Schedule a Response" CTA — DONE (2026-04-11)

**Result:** Frontend builds clean (no type errors), lint clean, full backend suite still 242/242. Browser verification deferred to Chunk 21's E2E sweep.

### Files shipped
- `frontend/lib/types.ts` — added `PostStatus`, `POST_STATUS_LABELS`, `PresignRequest`, `PresignResponse`, `ScheduledPostCreate`, `ScheduledPostUpdate`, `ScheduledPostResponse`
- `frontend/lib/api.ts` — added `uploadFileWithProgress(uploadUrl, file, onProgress, signal)` using XMLHttpRequest (fetch has no upload progress events)
- `frontend/components/publishing/upload-dropzone.tsx` (NEW) — drag/drop dropzone, presign → PUT flow with progress bar, three states (idle/uploading/uploaded), 200MB cap, MIME type allowlist
- `frontend/components/publishing/scheduled-post-form.tsx` (NEW) — connection select, title, description, hashtags, datetime-local schedule, status guard for empty connections list
- `frontend/components/publishing/post-composer.tsx` (NEW) — two-column layout wrapping dropzone + form, optional "Inspired by" preview card spanning the top
- `frontend/app/(dashboard)/dashboard/posts/new/page.tsx` (NEW) — client-component route, reads `?inspired_by=<id>` query param, fetches connections + source video in parallel
- `frontend/components/discover/schedule-response-button.tsx` (NEW) — outlier-only CTA that routes to `/dashboard/posts/new?inspired_by=<id>`
- `frontend/components/discover/video-card.tsx` — wired the new button next to "Generate idea" (also gated to outliers with a DB ID)
- `frontend/components/layout/sidebar.tsx` — added "Posts" nav item with `Send` icon, renamed existing "Schedule" → "Calendar"
- `frontend/components/layout/mobile-nav.tsx` — same nav additions

### Backend additions in this chunk
- `backend/app/publishing/routes.py` — added `PUT /uploads/local/{file_key:path}` and `GET /uploads/local/{file_key:path}` (dev-only sinks for `LocalStorageBackend`). Both routes return 404 when the storage backend is `SupabaseStorageBackend`, so they're a no-op in production. Authentication: the file_key embeds `<team_uuid>/<random_uuid>/` so guessing it requires both UUIDs (same security model as a presigned URL). `include_in_schema=False` keeps them out of the OpenAPI spec.

### Verification
- [x] `npm run build` — clean, `/dashboard/posts/new` route shows up at 4.01 kB / 191 kB First Load JS
- [x] `npm run lint` — clean, no warnings
- [x] `pytest` — 242 / 242, no backend regressions from the new local upload sink routes

### Key decisions worth noting
1. **No new shadcn primitive added.** The connection picker uses a native `<select>` styled with the existing input classes — adding `shadcn select` would have meant a new package install. Native `<select>` is fine for a 1-2 item list.
2. **`XMLHttpRequest` instead of fetch for the upload.** Fetch has no upload-progress events (only download). XHR is the standard pattern, wrapped in a Promise via the new `uploadFileWithProgress` helper in `lib/api.ts`.
3. **Local upload sink routes are gated by `isinstance(storage, LocalStorageBackend)`** at request time. This means the same code is safe to ship to production — the routes exist but always 404 when the backend is Supabase Storage.
4. **The "Schedule a response" button is a separate component** (`ScheduleResponseButton`), not inlined in `video-card.tsx`. Mirrors the existing `ContentBriefButton` pattern — keeps the card component lean and lets each button manage its own auth/visibility logic.
5. **`inspired_by_video_id` flows through the URL**, not through context or state. `?inspired_by=<id>` → `useSearchParams` → fetch the video → render in the composer header. No global state needed.

---

## ⏳ Chunk 20 — Original task list (kept for reference)

**Plan reference:** `synthetic-crafting-umbrella.md` §17 → Chunk 20

**Goal:** A user can click "Schedule a response" on any outlier in `/discover`, land on a composer, drag-drop a video, fill caption + schedule time + platform, and save. The post hits the backend with `inspired_by_video_id` pre-filled.

**Test target:** 0 (manual browser verify; covered by Chunk 21 E2E)

### Pre-flight
- [ ] Re-read `frontend/lib/api.ts` for the existing apiAuth pattern (so new functions match shape)
- [ ] Re-read `frontend/components/discover/video-card.tsx` to see where "Generate idea" lives (the new button slots in next to it)
- [ ] Re-read `frontend/lib/supabase/client.ts` — direct browser PUTs don't need Supabase JS for the dev/local backend, but we may need `createSignedUploadUrl` for production
- [ ] Confirm `frontend/components/ui/dialog.tsx` exists from shadcn (it does — used by content-brief-dialog)

### Frontend implementation — types + API client
- [ ] Edit `frontend/lib/types.ts` — add `ScheduledPost`, `ScheduledPostCreate`, `ScheduledPostUpdate`, `PresignResponse`, `PostStatus` enum (mirror of backend Pydantic)
- [ ] Edit `frontend/lib/api.ts` — add publishing client functions:
  - `presignUpload(filename, contentType)` → `PresignResponse`
  - `createPost(payload)` → `ScheduledPost`
  - `listPosts({ status?, cursor?, limit? })` → `{ items, next_cursor, has_more }`
  - `getPost(id)` → `ScheduledPost`
  - `updatePost(id, payload)` → `ScheduledPost`
  - `deletePost(id)` → `void`

### Frontend implementation — components
- [ ] Create `frontend/components/publishing/upload-dropzone.tsx`:
  - Drag/drop area + click-to-browse fallback
  - On drop: call `presignUpload(file.name, file.type)`
  - Use `XMLHttpRequest` PUT (not fetch — fetch has no progress events) to the returned `upload_url`
  - Progress bar bound to `xhr.upload.onprogress`
  - Emit `onUploaded({ file_key, file_size_bytes })` on completion
  - Error state with retry button
- [ ] Create `frontend/components/publishing/scheduled-post-form.tsx`:
  - Form state via `useState` (no react-hook-form yet — stay consistent with rest of app)
  - Fields: connection (select from connected accounts), title, description (textarea), hashtags (chip input), `scheduled_for` (datetime-local), hidden `inspired_by_video_id`
  - Submit button disabled until upload complete + required fields filled
  - On submit: call `createPost(payload)` → on success route to `/dashboard/posts/{id}`
- [ ] Create `frontend/components/publishing/post-composer.tsx`:
  - Wraps `<UploadDropzone>` + `<ScheduledPostForm>` in a two-column layout
  - Left column: dropzone + filename + size + replace button
  - Right column: form
  - Top of page: "Inspired by" preview card (only if `inspired_by_video_id` set)

### Frontend implementation — pages + nav
- [ ] Create `frontend/app/(dashboard)/dashboard/posts/new/page.tsx`:
  - Server component reads `?inspired_by=<video_id>` query param
  - Fetches the source video for the preview card if `inspired_by` is set
  - Fetches the team's `PlatformConnection` list for the connection picker
  - Passes data to `<PostComposer>` client component
- [ ] Edit `frontend/components/discover/video-card.tsx` — add "Schedule a response" button:
  - Only renders on outlier-tagged videos AND when user is authenticated
  - Routes to `/dashboard/posts/new?inspired_by={video.id}`
  - Visually distinct from existing "Generate idea" button (e.g., outline variant)
- [ ] Edit `frontend/components/shared/sidebar.tsx` — add nav items:
  - "Posts" → `/dashboard/posts`
  - "Calendar" → `/dashboard/calendar`

### Verification (browser, manual)
- [ ] `npm run build` — clean, no type errors
- [ ] `npm run lint` — clean
- [ ] Visit `/discover`, search for a topic, find an outlier → "Schedule a response" button visible
- [ ] Click → land on `/dashboard/posts/new?inspired_by=<id>` → composer renders, "Inspired by" card shows source video
- [ ] Drag a small video file → progress bar runs to 100% → "Uploaded" state shown
- [ ] Fill form (title, description, schedule for 1 minute in the future) → submit → redirect to detail page
- [ ] Reload backend `/api/v1/publishing/scheduled-posts` → row exists with `status=scheduled`, `inspired_by_video_id` populated, `created_by` set

---

## ✅ Chunk 21 — Calendar + Posts List + Post Detail + Browser E2E — DONE (2026-04-11)

**Result:** 244 / 244 backend tests passing (+2 new factory tests). Frontend builds clean, lint clean. Browser E2E sweep ran end-to-end via Chrome MCP, surfacing **3 real bugs** which were all fixed during the sweep. GIF exported.

### Bugs found and fixed during the sweep
1. **Content brief modal renders empty forever** (`content-brief-dialog.tsx`) — the auto-fetch logic lived in `handleOpenChange`, which Radix UI only calls for its own internal state transitions (trigger click, Escape). Parent-controlled `open={true}` never fires it. Replaced with a `useEffect` keyed on `open`.
2. **Calendar API returns "Request validation failed"** (`calendar/page.tsx`) — page passed `limit=200` but `PaginationParams` enforces `le=100`. Replaced with cursor pagination (5 pages × 100 = up to 500, plenty for a month view).
3. **Publish worker fails with YouTube 401 in dev** (`publishers/factory.py`) — factory always registered the real `YouTubeShortsPublisher` even when Google OAuth env vars were missing, so mock OAuth tokens were sent to `googleapis.com` and rejected. Factory now checks `isinstance(oauth_provider, MockOAuthProvider)` and registers `MockPublisher` for YouTube + Instagram when OAuth is mocked. **+4 new factory tests** cover both real and mock branches for both platforms.

### Browser E2E sweep results
- ✅ Sign up new user (`e2e+1744388000@cliplift.test`) → `/dashboard` → onboarding cards rendered ("Welcome to Cliplift" + 4 cards)
- ✅ Niche created (`E2E Fitness Test`)
- ✅ Discover-trends worker run via curl: `processed=100, errors=0, videos_added=80`
- ✅ Niche feed: 1 outlier with `Generate idea` + `Schedule a response` buttons (rest were below the 3.0σ threshold)
- ✅ "Generate idea" → modal → fetches and renders Hook analysis, Format, Caption, 6 hashtags, CTA (after Bug #1 fix)
- ✅ "Schedule a response" → composer with `inspired_by` query param + "Inspired by" preview card showing source video
- ✅ OAuth mock connection: `youtube_user_e79eecd7` connected, "Connection successful" banner
- ✅ Composer with 1 connection in select, dropzone visible
- ✅ Synthetic File dropped → presign → PUT to local sink → "uploaded" state with filename + size
- ✅ Form submit → post created (id `21bd60f4-...`) → redirect to detail page
- ✅ Calendar shows "E2E test post" pill on today's cell with month nav working (April 2026, today highlighted) — after Bug #2 fix
- ✅ Publish-scheduled worker run via curl: `processed=1, succeeded=1, failed=0` — after Bug #3 fix
- ✅ Detail page green "Published" banner: "Published 11/04/2026, 15:41:15", View on youtube link, "Platform ID: mock_21bd60f4"
- ✅ Posts list → "Published" filter tab → row visible with PostStatusBadge

### Files shipped
- `frontend/components/publishing/{post-status-badge,post-list-row,content-calendar}.tsx` (NEW)
- `frontend/app/(dashboard)/dashboard/{posts,posts/[id],calendar}/page.tsx` (NEW × 3)
- `frontend/components/layout/{sidebar,mobile-nav}.tsx` (edits — Calendar nav repointed to `/dashboard/calendar`)
- `frontend/components/discover/content-brief-dialog.tsx` (edit — Bug #1 fix, useEffect-based auto-fetch)
- `frontend/app/(dashboard)/dashboard/calendar/page.tsx` (edit — Bug #2 fix, cursor pagination)
- `backend/app/publishing/publishers/factory.py` (edit — Bug #3 fix, mock-fallback when OAuth provider is mocked)
- `backend/tests/test_publisher_factory.py` (edit — +4 tests for the new gating)

### Verification
- [x] `pytest` — **244 / 244** total (+2 over Chunk 20), zero regressions
- [x] `npm run build` clean
- [x] `npm run lint` clean
- [x] Full Week 3 + Week 4 browser sweep passed
- [x] GIF captured: `cliplift-week3-week4-e2e.gif` (872KB, 10 frames — partial highlight reel; the gif_creator tool clears frames on page refresh)

---

## ⏳ Chunk 21 — Original task list (kept for reference)

**Result:** Frontend builds clean, lint clean. Three new dashboard routes registered. Browser E2E sweep is the remaining step.

### Files shipped
- `frontend/components/publishing/post-status-badge.tsx` (NEW) — color-coded badge per status (publishing pulses)
- `frontend/components/publishing/post-list-row.tsx` (NEW) — list row with platform badge + scheduled time + status badge + error message
- `frontend/components/publishing/content-calendar.tsx` (NEW) — read-only month grid using `date-fns`, status-colored pills, "+N more" overflow links, today highlight, prev/next/today nav
- `frontend/app/(dashboard)/dashboard/posts/page.tsx` (NEW) — list view with status filter tabs (All / Scheduled / Publishing / Published / Failed / Draft), cursor pagination handled by backend
- `frontend/app/(dashboard)/dashboard/posts/[id]/page.tsx` (NEW) — detail view with status banners (green for published with link, red for failed with error_message), metadata grid, hashtags, file_key, "Inspired by" link
- `frontend/app/(dashboard)/dashboard/calendar/page.tsx` (NEW) — calendar route, fetches up to 200 posts and filters out drafts before passing to `<ContentCalendar>`
- `frontend/components/layout/sidebar.tsx` + `mobile-nav.tsx` — fixed Calendar nav to point at `/dashboard/calendar` (was still pointing at the dead `/dashboard/schedule` route)

### Implementation verification
- [x] `npm run build` — clean, all 3 new routes show up: `/dashboard/calendar` (11.8 kB), `/dashboard/posts` (5.55 kB), `/dashboard/posts/[id]` (2.6 kB)
- [x] `npm run lint` — clean, no warnings
- [x] No new dependencies — uses the existing `date-fns@4.1` for the calendar grid

### Browser E2E sweep — PENDING

**Pre-flight (do these once before the sweep):**
- [ ] Place a small sample video at `backend/tests/fixtures/sample.mp4` (under 10 MB)
- [ ] `make dev` running (backend :8000 + frontend :3000)
- [ ] Local Supabase running (`make supabase-start`)

**Week 3 sweep (folds in deferred Chunk 16):**
- [ ] Sign up new user → land on `/dashboard` → see onboarding cards
- [ ] Track a creator + create a niche → reload `/dashboard` → analytics dashboard with stat cards + recent outliers feed
- [ ] Visit creator detail → follower growth `<LineChart>` (will show `<ChartEmpty>` until worker runs)
- [ ] `make worker-discover` → reload → chart populates
- [ ] Visit niche detail → platform breakdown bar chart + "videos discovered per day" line
- [ ] `/discover` → search → outlier → "Generate idea" → modal opens → mock content brief renders
- [ ] Click "Generate idea" again → instant cache hit (no spinner)
- [ ] Sign out → middleware redirect

**Week 4 E2E sweep:**
- [ ] Sign back in → connect YouTube via mock OAuth
- [ ] `/discover` → search → outlier → "Schedule a response"
- [ ] Composer opens with `inspired_by` pre-filled → upload sample video → progress bar → uploaded
- [ ] Fill caption "test from e2e", set `scheduled_for = now() + 1 minute`, hashtags `["test"]` → submit
- [ ] Land on detail page → status `scheduled`
- [ ] `/dashboard/calendar` → see post pill on today's cell
- [ ] Wait 1 minute, `make worker-publish` → returns `{succeeded: 1}`
- [ ] Reload detail → status `published`, `platform_post_id` visible (mock value)
- [ ] `/dashboard/posts` → "Published" filter tab → row visible
- [ ] Sign out → sign back in → all posts persisted

### Wrap-up (after sweep)
- [ ] Capture a GIF of the full Week 4 flow via the claude-in-chrome `gif_creator` for the README
- [ ] Add bugs found + fixes to the Review section below
- [ ] Update `MEMORY.md` project memory: mark Week 4 as shipped, set "next: Week 5 — Billing"

---

## ⏳ Chunk 21 — Original task list (kept for reference)

**Plan reference:** `synthetic-crafting-umbrella.md` §17 → Chunk 21

**Goal:** A `/dashboard/calendar` view showing scheduled posts on a month/week grid, a `/dashboard/posts` list view, and a full E2E pass that exercises both Week 3 (deferred Chunk 16) and Week 4 features in a single browser session.

**Test target:** 0 (manual browser verify)

### Pre-flight
- [ ] Confirm `make worker-publish` target exists from Chunk 19
- [ ] Confirm Supabase + dev backend + frontend are runnable concurrently via `make dev`
- [ ] Place a small sample video at `tests/fixtures/sample.mp4` (under 10MB) for the E2E upload step

### Frontend implementation — components
- [ ] Create `frontend/components/publishing/post-status-badge.tsx`:
  - Color-coded badge by status: gray (draft), blue (scheduled), yellow (publishing), green (published), red (failed)
  - Reuses shadcn `<Badge>` primitive
- [ ] Create `frontend/components/publishing/post-list-row.tsx`:
  - Row component: thumbnail (or video icon if no thumbnail yet), title, platform icon, scheduled_for, `<PostStatusBadge>`, actions (Edit / Delete)
- [ ] Create `frontend/components/publishing/content-calendar.tsx`:
  - Month grid (7 columns × 5-6 rows depending on month)
  - Each cell shows post pills colored by status (max 3 visible, "+N more" overflow link)
  - Click pill → opens shadcn `<Sheet>` drawer with post details + "Edit" link
  - **Read-only this week** — drag-to-reschedule deferred to Phase 2

### Frontend implementation — pages
- [ ] Create `frontend/app/(dashboard)/dashboard/posts/page.tsx`:
  - List view with status filter tabs: All / Draft / Scheduled / Published / Failed
  - Cursor-paginated via `listPosts`
  - Empty state via existing `<EmptyState>` component
- [ ] Create `frontend/app/(dashboard)/dashboard/posts/[id]/page.tsx`:
  - Detail view: full post metadata, status, platform_post_id (link to YouTube/Instagram on success), error_message on failure
  - Edit button (only if status in editable set) → routes to composer in edit mode
  - Delete button with confirmation dialog
- [ ] Create `frontend/app/(dashboard)/dashboard/calendar/page.tsx`:
  - Server component fetches `listPosts({ status: 'scheduled', limit: 200 })`
  - Passes data to `<ContentCalendar>` client component
  - Empty state when no scheduled posts

### Verification — Week 3 sweep (folds in deferred Chunk 16)
- [ ] Sign up new user → land on `/dashboard` → see onboarding cards (zero-data branch)
- [ ] Track a creator + create a niche → reload `/dashboard` → see analytics dashboard with stat cards + recent outliers feed
- [ ] Visit creator detail → see follower growth `<LineChart>` (will show `<ChartEmpty>` until worker runs)
- [ ] Trigger discover-trends worker via `make worker-discover` → reload → confirm chart populates
- [ ] Visit niche detail → see platform breakdown bar chart + "videos discovered per day" line at top of page
- [ ] Visit `/discover` → search → find outlier → click "Generate idea" → modal opens → mock content brief renders (hook analysis, format, caption, hashtags, CTA)
- [ ] Click "Generate idea" again on the same video → confirm instant cache hit (no spinner)
- [ ] Sign out → confirm middleware redirects protected routes to login

### Verification — Week 4 E2E sweep
- [ ] Sign back in (or sign up fresh user) → connect YouTube via mock OAuth (existing flow from Chunk 10)
- [ ] Visit `/discover` → search "ai productivity" → find an outlier → click "Schedule a response"
- [ ] Composer opens with `inspired_by` pre-filled → upload `tests/fixtures/sample.mp4` → progress completes
- [ ] Fill caption "test from e2e", set `scheduled_for = now() + 1 minute`, hashtags `["test"]` → submit
- [ ] Land on detail page → `status = scheduled`
- [ ] Visit `/dashboard/calendar` → see post pill on today's cell
- [ ] Wait 1 minute, then `make worker-publish` → returns `{succeeded: 1}`
- [ ] Reload detail page → `status = published`, `platform_post_id` visible (mock value from `MockPublisher`)
- [ ] Visit `/dashboard/posts` → "Published" filter tab → see the post in the list
- [ ] Sign out → confirm middleware redirect
- [ ] Sign back in → confirm all posts persisted

### Wrap-up
- [ ] Capture a GIF of the full Week 4 flow (composer → upload → schedule → worker → published) via the claude-in-chrome `gif_creator` for the README
- [ ] Add a Review entry below: bugs found + fixed, GIF link, final test count
- [ ] Update `MEMORY.md` project memory: mark Week 4 as shipped, set "next: Week 5 — Billing"

---

## ⏳ Chunk 22 — Plan Tier Config + `trial_ends_at` Migration + MockStripeClient — NEXT

**Plan reference:** `synthetic-crafting-umbrella.md` §18 → Chunk 22
**Test target:** +12 (244 → 256)

### Pre-flight
- [ ] Confirm `Team.plan: str` exists in `auth/models.py:64` (it does — defaults to `"creator"`)
- [ ] Confirm `Team.stripe_customer_id` exists (`auth/models.py:37`)
- [ ] Confirm `STRIPE_SECRET_KEY` / `STRIPE_PRICE_*` env vars in `config.py` (they do)
- [ ] Confirm `stripe>=11.4.0` in `pyproject.toml` (it is)
- [ ] Re-read `app/common/storage.py` for the mock-first factory pattern to mirror

### Backend implementation
- [ ] Edit `app/auth/models.py` — add `Team.trial_ends_at: Mapped[datetime | None]`
- [ ] `make migrate-create MSG="team trial_ends_at"` — review the generated migration before committing; ensure backfill statement sets `trial_ends_at = now() + interval '7 days'` for existing teams
- [ ] Create `app/billing/__init__.py`, `plans.py` (PlanLimits + PLAN_LIMITS dict), `base.py` (StripeClient Protocol), `mock.py` (MockStripeClient), `factory.py` (build_stripe_client)
- [ ] Edit `app/main.py` — `app.state.stripe_client = build_stripe_client(settings)` in lifespan
- [ ] Edit `app/auth/schemas.py` — extend `TeamResponse` with `plan`, `trial_ends_at`, `is_trial_active` (computed)
- [ ] Edit `app/auth/routes.py` — `GET /api/v1/teams/me` returns the extended response

### Tests (+12)
- [ ] `tests/test_plan_limits.py` — every plan tier has all required fields, monotonic limits
- [ ] `tests/test_stripe_mock.py` — checkout shape, synthetic webhook event, signature accepts mock header, factory picks mock when key empty
- [ ] `tests/test_team_trial.py` — new teams get 7-day trial, `is_trial_active` flips correctly, migration backfill works

### Verification
- [ ] `pytest tests/test_plan_limits.py tests/test_stripe_mock.py tests/test_team_trial.py -v` — 12 green
- [ ] `make migrate` — clean
- [ ] `pytest` — total 256, no regressions
- [ ] `make backend` then `curl http://localhost:8000/api/v1/teams/me` (with auth) returns the extended shape including `trial_ends_at`

---

## ⏳ Chunk 23 — Real Stripe Wiring — PLANNED

**Plan reference:** `synthetic-crafting-umbrella.md` §18 → Chunk 23
**Test target:** +14 (256 → 270)

### Pre-flight
- [ ] Confirm `STRIPE_PRICE_CREATOR / STRIPE_PRICE_TEAM / STRIPE_PRICE_AGENCY` env vars exist in `config.py`
- [ ] Re-read `app/publishing/oauth_routes.py` — webhook routes need raw body access for signature verification

### Backend implementation
- [ ] Create `app/billing/real.py` — `RealStripeClient` wrapping `stripe.checkout.Session`, `stripe.billing_portal.Session`, `stripe.customers.create`, `stripe.Webhook.construct_event`
- [ ] Edit `app/billing/factory.py` — `build_stripe_client` returns `RealStripeClient` when `STRIPE_SECRET_KEY` is set
- [ ] Create `app/billing/schemas.py` — `CheckoutSessionRequest`, `CheckoutSessionResponse`, `BillingPortalResponse`, `BillingEvent` (internal normalized)
- [ ] Create `app/billing/service.py` — `create_checkout_session`, `create_billing_portal_session`, `handle_webhook_event`. Webhook dispatch:
  - `checkout.session.completed` → `team.plan = parsed.plan`, clear `trial_ends_at`
  - `customer.subscription.updated` → update `team.plan` only; do NOT touch `trial_ends_at`
  - `customer.subscription.deleted` → **HARD CUTOFF**: `team.plan = "cancelled"`, `trial_ends_at = None`. No automatic trial reissue (would create cancel→trial→cancel loophole). Reactivation = fresh checkout.
- [ ] Create `app/billing/routes.py` — `POST /billing/checkout` (auth), `POST /billing/portal` (auth), `POST /billing/webhook` (NO auth — Stripe signs)
- [ ] Edit `app/main.py` — register `billing_router`

### Tests (+14)
- [ ] `tests/test_stripe_real.py` — mocks `stripe.checkout.Session.create`, asserts line items + metadata + customer creation flow
- [ ] `tests/test_billing_routes.py` — auth required on /checkout + /portal, returns mock URL in dev
- [ ] `tests/test_billing_webhook.py` — checkout-completed flips plan + clears trial; **subscription-deleted hard-cancels (`plan="cancelled"`, `trial_ends_at=None`)**; subscription-updated changes plan but leaves trial alone; invalid signature → 401; idempotency; reactivation flow (cancelled team completes checkout → back to paid plan)
- [ ] `tests/test_billing_portal.py` — auth required, errors when no customer

### Verification
- [ ] `pytest tests/test_billing_*.py tests/test_stripe_real.py -v` — 14 green
- [ ] `pytest` — total 270
- [ ] `curl -X POST .../billing/checkout` returns mock URL in dev mode

---

## ⏳ Chunk 24 — Plan Enforcement Middleware (cancel + trial-expired gates) — PLANNED

**Plan reference:** `synthetic-crafting-umbrella.md` §18 → Chunk 24
**Test target:** +27 (270 → 297)

### Pre-flight
- [ ] Re-read `app/common/ratelimit.py` for the per-user rate limit pattern — Chunk 24 layers per-plan modifiers on top
- [ ] List every endpoint that creates a billable resource (creators/track, niches POST/PUT/DELETE, scheduled-posts POST/PATCH/DELETE, uploads/presign, connections/{platform}/authorize, discovery/generate-idea)
- [ ] Decide which DELETE endpoints bypass `require_active_plan` (cleanup operations should still work for cancelled teams — see decision_billing memory)

### Backend implementation
- [ ] Create `app/billing/enforcement.py`:
  - `PlanLimitExceeded(HTTPException(402))` with structured envelope: `limit_name`, `current_plan`, `suggested_plan`
  - **`require_active_plan(team) -> Team`** — FastAPI dependency. Two failure modes:
    1. `team.plan == "cancelled"` → raises with `limit_name="subscription_cancelled"`
    2. `team.trial_ends_at < now() AND team.stripe_customer_id IS NULL` → raises with `limit_name="trial_expired"` (closes the gap where a never-paid user's trial expires and no Stripe event ever fires)
    Otherwise passes the team through. Every write endpoint depends on it.
  - `enforce_creator_tracking_limit(db, team)` — count vs `tracked_creators`
  - `enforce_platform_connection_limit(db, team)` — distinct platforms vs `max_platforms` (Creator = 1)
  - `enforce_scheduling_enabled(team)` — gate on `scheduling: bool` (Creator = False)
  - `enforce_api_access(team)` — placeholder for Phase 2
- [ ] Edit `app/common/errors.py` — handle 402 in standard envelope, surface `limit_name` / `current_plan` / `suggested_plan` under `error.details`
- [ ] Edit `app/creators/routes.py` — `POST /creators/track` depends on `require_active_plan` AND calls `enforce_creator_tracking_limit`
- [ ] Edit `app/discovery/niche_routes.py` — `POST /niches`, `PUT /niches/{id}`, `DELETE /niches/{id}` depend on `require_active_plan`
- [ ] Edit `app/publishing/routes.py` — `POST /uploads/presign`, `POST /scheduled-posts`, `PATCH /scheduled-posts/{id}`, `DELETE /scheduled-posts/{id}` depend on `require_active_plan`; presign + post-create also call `enforce_scheduling_enabled`
- [ ] Edit `app/publishing/oauth_routes.py` — `POST /connections/{platform}/authorize` depends on `require_active_plan` AND calls `enforce_platform_connection_limit`; **`DELETE /connections/{id}` does NOT depend on require_active_plan** (cancelled users can still disconnect to clean up)
- [ ] Edit `app/discovery/routes.py` — generate-idea depends on `require_active_plan`; per-plan rate-limit modulator (creator 10/h, team 50/h, agency unlimited)

### Tests (+27)
- [ ] `tests/test_enforcement.py`:
  - 9 creator-tracking tests (under/at/over × 3 tiers)
  - 3 platform-connection tests (Creator with 0 → success; Creator with 1 attempting 2nd → 402; Team with 3 attempting 4th → success)
  - 2 scheduling-disabled tests (Creator hits 402 on presign + post create)
  - 3 AI brief rate-limit-modulator tests
  - 3 cross-team isolation tests
  - **4 cancelled-team tests:**
    - cancelled team write attempts (track/post/connect/generate-brief) → all return 402 with `limit_name="subscription_cancelled"`
    - cancelled team CAN read existing creators/posts/niches/dashboard (GET endpoints unaffected)
    - cancelled team CAN delete connections (DELETE bypasses require_active_plan)
    - cancelled team that completes fresh checkout flips to paid plan and writes work again
  - **3 trial-expired tests:**
    - active trial (`trial_ends_at` in future, no `stripe_customer_id`) → write succeeds
    - expired trial AND `stripe_customer_id IS NULL` → 402 with `limit_name="trial_expired"`
    - expired trial BUT `stripe_customer_id` set (paid at least once) → write succeeds (proves the AND condition only gates never-paid users)

### Verification
- [ ] `pytest tests/test_enforcement.py -v` — 27 green
- [ ] `pytest` — total 297, no regressions
- [ ] Manual smoke: track 4 creators on Creator tier → 4th returns 402 with helpful detail
- [ ] Manual smoke: connect 2nd platform on Creator tier → 402 with `limit_name="max_platforms"`, `suggested_plan="team"`
- [ ] Manual smoke: cancel a team (via DB), try to track → 402 with `limit_name="subscription_cancelled"`; GET /creators still returns the existing list
- [ ] Manual smoke: backdate `trial_ends_at` to yesterday on a never-paid team → next write returns 402 with `limit_name="trial_expired"`; set any `stripe_customer_id` → writes resume

---

## ⏳ Chunk 25 — Settings UIs (Billing + Team + Connections) — PLANNED

**Plan reference:** `synthetic-crafting-umbrella.md` §18 → Chunk 25

### Pre-flight
- [ ] `npx shadcn add toast sonner` — needed in Chunk 27 too but let's add early
- [ ] Confirm `frontend/components/shared/empty-state.tsx` accepts an `action` prop (it does)

### Frontend implementation
- [ ] Edit `frontend/lib/types.ts` — `BillingPlan`, `TeamWithUsage`, `BillingUsage`
- [ ] Edit `frontend/lib/api.ts` — `getBilling()`, `createCheckoutSession()`, `createBillingPortal()`
- [ ] Create `components/billing/{plan-card,usage-meter,trial-banner}.tsx`
- [ ] Create `app/(dashboard)/dashboard/settings/layout.tsx` — left rail nav (Profile / Billing / Team / Connections)
- [ ] Create `app/(dashboard)/dashboard/settings/billing/page.tsx`
- [ ] Create `app/(dashboard)/dashboard/settings/team/page.tsx`
- [ ] Edit `app/(dashboard)/dashboard/settings/connections/page.tsx` — gate "Connect" button on `max_platforms` cap
- [ ] Wire trial banner into `app/(dashboard)/layout.tsx`

### Verification (browser, manual)
- [ ] `npm run build` clean
- [ ] `/dashboard/settings/billing` shows current plan + usage meters + 3 plan options
- [ ] Click "Upgrade to Team" → mock checkout URL
- [ ] Synthetic webhook → reload → plan flipped to Team
- [ ] Track 4th creator on Creator tier → toast with upgrade CTA

---

## ⏳ Chunk 26 — Landing Page + `/compare/virlo` SEO Page — PLANNED

**Plan reference:** `synthetic-crafting-umbrella.md` §18 → Chunk 26

### Pre-flight
- [ ] Decide on hero illustration / placeholder
- [ ] Pull pricing table copy from `tmp/STRATEGY.md`

### Frontend implementation
- [ ] Edit `app/page.tsx` — full marketing landing (currently just redirects to /dashboard)
- [ ] Create `app/compare/virlo/page.tsx`
- [ ] Create `components/marketing/{pricing-table,feature-grid,footer}.tsx`
- [ ] Edit `app/layout.tsx` — OG meta defaults

### Verification (browser, manual)
- [ ] `/` (signed out) — landing page renders, no redirect
- [ ] `/compare/virlo` — comparison table renders
- [ ] Lighthouse: LCP < 2.5s, CLS < 0.1, perf > 90 on both pages
- [ ] OG tags present in `<head>`

---

## ⏳ Chunk 27 — Polish Pass + Week 5 Browser E2E — PLANNED

**Plan reference:** `synthetic-crafting-umbrella.md` §18 → Chunk 27

### Pre-flight
- [ ] `make dev` running, Supabase running, sample.mp4 in fixtures (already there from Chunk 21)

### Polish pass
- [ ] Mount `<Toaster />` in `app/layout.tsx`
- [ ] Wrap `apiAuth` with global error handler that surfaces 402/429/500 as toasts
- [ ] Loading state sweep — `<Skeleton>` on every dashboard route
- [ ] Empty state sweep — `<EmptyState>` on every list view
- [ ] Error boundary on dashboard layout

### Week 5 E2E sweep (Chrome MCP)
- [ ] Sign up new user → trial banner visible
- [ ] Track 3 creators on Creator tier → success
- [ ] 4th tracking attempt → toast with upgrade CTA
- [ ] Click "Upgrade" → /dashboard/settings/billing
- [ ] "Upgrade to Team" → mock checkout URL → fire synthetic webhook → plan flips
- [ ] Reload billing → "Team — $79/mo", usage 3/25
- [ ] 4th creator now succeeds
- [ ] Connect a 2nd platform on Team tier → success (Creator would have blocked)
- [ ] `/` and `/compare/virlo` (incognito) — render correctly
- [ ] Lighthouse on both pages > 90

### Wrap-up
- [ ] Capture Week 5 GIF
- [ ] Update `MEMORY.md` — mark Week 5 shipped, set "next: Week 6 deploy"

## Later — Week 6: Deploy & Launch
**Plan reference:** `synthetic-crafting-umbrella.md:735-747`

- [ ] Railway deploy (FastAPI auto-sleep)
- [ ] Vercel deploy (Next.js frontend)
- [ ] QStash cron schedules configured against production worker URLs (including `publish-scheduled` at 5min)
- [ ] Domain + SSL (CORS already done in Week 1)
- [ ] Sentry + basic logging
- [ ] Seed 10 niches with real data for demo
- [ ] Beta invite 10–20 creators
- [ ] Product Hunt launch prep
- [ ] "Virlo Alternative" SEO blog posts
- [ ] Creator partnership outreach
- [ ] Reddit / Discord community posts

---

## Review

### Chunk 17 — DONE 2026-04-11
- Shipped 10 files (4 new, 6 edits) in `app/common/`, `app/publishing/`, `app/config.py`, `app/main.py`, plus 3 test files
- 49 new tests (212 total, +49 over the 163 baseline) — zero regressions
- Two latent bugs caught and fixed during the build:
  1. **Storage factory key was wrong** — was triggering off `SUPABASE_SERVICE_ROLE_KEY` alone, which is set when local Supabase is running, so dev tests would accidentally hit Supabase Storage and fail because the bucket didn't exist. Replaced with a `STORAGE_BACKEND` setting (`auto` / `local` / `supabase`) where `auto` only picks Supabase in `ENVIRONMENT=production`. Five new factory tests cover the matrix.
  2. **`field_validator` raising `ValueError` produced JSON-unserializable error responses** because Pydantic v2 stuffs the raw exception in `ctx.error` and `JSONResponse` chokes on it. Replaced with `Literal[...]` for `content_type` and `pattern` constraint for `filename` — Pydantic core emits clean `literal_error` / `string_pattern_mismatch` natively.
- Key design decisions logged in `synthetic-crafting-umbrella.md` §17

### Chunk 21 — DONE 2026-04-11 (E2E sweep complete, 3 bugs fixed live)
- Frontend code: 7 new files + nav repoint, all green build/lint
- 3 real bugs found and fixed during the sweep:
  1. `content-brief-dialog.tsx` auto-fetch was wired to Radix `onOpenChange` which doesn't fire on controlled-prop changes — switched to `useEffect`
  2. Calendar page passed `limit=200` but backend enforces `le=100` — switched to cursor pagination
  3. Publisher factory always registered real `YouTubeShortsPublisher` even with mock OAuth tokens — added `isinstance(oauth, MockOAuthProvider)` gating for YouTube + Instagram, +4 new factory tests
- Browser sweep verified the entire insight → publish → measure loop end-to-end via Chrome MCP
- 244 / 244 backend tests passing (+2 net)
- GIF: `cliplift-week3-week4-e2e.gif` (partial highlight reel — gif_creator tool cleared frames on page refresh)

### Chunk 21 — code shipped 2026-04-11 (E2E sweep pending) — superseded above
- 7 new files: `post-status-badge.tsx`, `post-list-row.tsx`, `content-calendar.tsx`, `posts/page.tsx`, `posts/[id]/page.tsx`, `calendar/page.tsx`, plus the nav fix
- Frontend builds clean, lint clean, all 3 new routes registered
- Calendar uses `date-fns` (already in deps), no new packages
- The `/dashboard/schedule` dead link was an existing bug — fixed in this chunk by re-pointing the nav at the new `/dashboard/calendar` route
- Browser E2E sweep — covering Week 3 + Week 4 in one session — is the remaining step. Pre-flight: drop a sample video at `backend/tests/fixtures/sample.mp4`, `make dev` running, Supabase running.

### Chunk 20 — DONE 2026-04-11
- Shipped 8 new files (1 backend route addition + 7 frontend) plus 4 frontend edits
- Frontend builds clean, lint clean, no backend regressions
- New flow: outlier in `/discover` → "Schedule a response" → `/dashboard/posts/new?inspired_by=<id>` → drag/drop video → progress bar → fill form → submit → redirect to detail page
- Local upload sink (`PUT /uploads/local/{file_key:path}`) added so dev uploads actually work — gated by `isinstance(storage, LocalStorageBackend)` so it's a no-op in production. `include_in_schema=False` keeps it out of OpenAPI.
- `XMLHttpRequest`-based upload helper in `lib/api.ts` because fetch has no upload-progress events.
- New "Posts" nav item with `Send` icon; existing "Schedule" entry renamed to "Calendar" (will be wired to the calendar route in chunk 21).

### Chunk 19 — DONE 2026-04-11
- Shipped 5 files: `workers/publish_scheduled.py` (NEW), `workers/routes.py` (edit), `workers/discover_trends.py` (latent bug fix), `Makefile` (worker-publish target), `tests/test_publish_worker.py` (NEW, 8 tests)
- 8 new tests, all green (242 total, +8 over Chunk 18)
- Worker uses `SELECT FOR UPDATE SKIP LOCKED` for safe concurrent pickup. Per-post try/except with rollback + refetch ensures even mid-publish failures result in `failed` status, never stuck `publishing`
- Fixed a real latent bug in `discover_trends`: missing `ORDER BY` meant >100 active niches could leave brand-new niches unprocessed indefinitely. Now ordered NULLS FIRST so unprocessed niches always lead.
- Fixture lesson: any test fixture that creates SQLAlchemy sessions outside the conftest `client` fixture must call `await engine.dispose()` in teardown to avoid "Future attached to a different loop" errors when the next test starts in a fresh event loop.

### Chunk 18 — DONE 2026-04-11
- Shipped 9 new files in `app/publishing/publishers/` + `publisher_router.py` + 4 test files
- 22 new tests, all green on first run (234 total, +22 over Chunk 17)
- Extended `OAuthProvider` ABC with `refresh_access_token` — Google + Meta + Mock all implement it
- Hand-rolled YouTube `videos.insert` multipart upload via httpx — no `google-api-python-client` dep added
- Shared `_credentials.py` helper handles decrypt → expiry check (5-min safety margin) → refresh → encrypted persist for both real publishers
- Token refresh persistence verified: tests assert encrypted token in DB decrypts to the refreshed value AND the new Bearer header carries it
- One small structural choice worth noting: Publisher.publish accepts both `video_bytes` (YouTube binary upload) AND `video_url` (Instagram Reels Graph API fetches from URL). Each publisher uses what it needs; mock ignores both.

### Chunks 19–21 — _(populated as each chunk lands)_
