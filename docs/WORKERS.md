# Workers

> QStash-triggered HTTP endpoints. Not background processes — QStash POSTs to them on a cron schedule.

## Architecture

Workers are regular FastAPI routes under `/api/v1/workers/`. QStash sends HTTP POST requests on a schedule. Each worker validates the QStash signature, runs its logic, and returns a JSON summary. The server can auto-sleep between triggers (Railway compatibility).

```
QStash (Upstash managed)
  ├── POST /workers/scrape-creators     (daily)
  ├── POST /workers/scrape-videos       (6-hourly)
  ├── POST /workers/discover-trends     (hourly)
  ├── POST /workers/publish-scheduled   (every 5 minutes)
  └── POST /workers/collect-analytics   (daily)
```

## Authentication

All worker routes are gated by `verify_qstash_signature` dependency (`workers/middleware.py`).

**Production:** QStash signs every request with a JWT in the `Upstash-Signature` header. Verified against `QSTASH_CURRENT_SIGNING_KEY` with fallback to `QSTASH_NEXT_SIGNING_KEY` (key rotation).

**Dev mode** (no signing keys configured): Workers accept `X-Dev-Worker-Token` header matching `ENCRYPTION_KEY`:

```bash
# Dev triggers via Makefile (reads ENCRYPTION_KEY automatically, passes max_age_hours=0)
make worker-creators
make worker-videos
make worker-discover
make worker-publish
make worker-analytics

# Manual curl
curl -X POST http://localhost:8000/api/v1/workers/scrape-creators \
  -H "X-Dev-Worker-Token: $ENCRYPTION_KEY"
```

## Workers

### scrape-creators

**Schedule:** Daily. **File:** `workers/scrape_creators.py`

Refreshes metrics for tracked creators:
1. SELECT creators that are tracked by at least one team AND `last_scraped_at` is stale (> `max_age_hours`, default 24)
2. For each: call `DataProviderRouter.get_creator(platform, platform_id)`
3. Insert a `CreatorSnapshot` row (followers, total_videos, avg_views_30d)
4. Update denormalized columns on the `creators` table
5. Set `last_scraped_at = now()`

**Params:** `max_age_hours: int = 24` (query param, 0 = force all)

**Returns:** `{processed, errors, total}`

### scrape-videos

**Schedule:** Every 6 hours. **File:** `workers/scrape_videos.py`

Refreshes metrics + computes view velocity for tracked videos:
1. SELECT videos tracked by at least one team AND stale (> `max_age_hours`, default 6)
2. For each: call `DataProviderRouter.get_video_metrics(platform, video_id)`
3. Compute `view_velocity = (current_views - prev_views) / hours_elapsed` from the previous snapshot
4. Insert a `VideoSnapshot` row
5. Update denormalized `latest_*` columns on the `videos` table

**Params:** `max_age_hours: int = 6`

**Returns:** `{processed, errors, total}`

### discover-trends

**Schedule:** Hourly. **File:** `workers/discover_trends.py`

Auto-discovers videos for active niches:
1. SELECT active niches ordered by `last_analyzed_at ASC NULLS FIRST` (so new niches always run first), LIMIT 100
2. For each niche: build query from keywords, search across niche's platforms via `DataProviderRouter.search_videos`
3. Apply Z-score outlier detection per platform
4. Upsert `Video` rows for new results
5. Insert `NicheVideo` rows linking videos to the niche (idempotent — skips existing links)
6. Set `niche.last_analyzed_at = now()`

**Params:** `max_age_hours: int = 1`, `limit_per_platform: int = 20`, `niche_limit: int = 100`

**Returns:** `{processed, errors, total_niches, videos_added}`

**Important:** The `ORDER BY last_analyzed_at ASC NULLS FIRST` ensures brand-new niches always get processed first, even when there are >100 total active niches.

### publish-scheduled

**Schedule:** Every 5 minutes. **Timeout:** 120 seconds. **File:** `workers/publish_scheduled.py`

Publishes due scheduled posts:
1. `SELECT * FROM scheduled_posts WHERE status='scheduled' AND scheduled_for <= now() ORDER BY scheduled_for ASC LIMIT N FOR UPDATE SKIP LOCKED`
2. Flip status to `publishing` and COMMIT (releases lock, prevents double-pickup)
3. For each post:
   a. Load `PlatformConnection`, decrypt tokens
   b. Download bytes via `storage.download_bytes(post.file_key)`
   c. Get download URL via `storage.create_download_url(post.file_key)` (for Instagram)
   d. Call `publisher_router.get(platform).publish(db, connection, post, bytes, url)`
   e. On success: `status='published'`, set `platform_post_id`, `media_url`, `published_at`
   f. On failure: rollback, re-fetch post, `status='failed'`, set `error_message`
4. Return `{processed, succeeded, failed, errors: [...]}`

**Params:** `max_posts: int = 1` (query param, max 10)

**Concurrency safety:**
- `SELECT FOR UPDATE SKIP LOCKED` — multiple worker instances pick different posts
- Status flips to `publishing` inside the transaction that holds the lock
- Each post processed in its own try/except — one failure doesn't abort the batch
- Token refresh happens inside the publisher, persisted before the upload call

### collect-analytics

**Schedule:** Daily. **File:** `workers/collect_analytics.py`

Collects performance metrics for published posts — closes the "measure the results" loop:
1. SELECT `scheduled_posts` where `status='published'` AND `platform_post_id IS NOT NULL`
2. For each: call `DataProviderRouter.get_video_metrics(platform, platform_post_id)`
3. Insert a `PostAnalytics` snapshot (views, likes, comments, shares)
4. Mock provider returns deterministic metrics for mock post IDs — no error in dev

**Params:** `max_age_hours: int = 24`

**Returns:** `{processed, errors, total}`

**Note:** This worker queries metrics for your *own published content* (via connected-account OAuth tokens or mock), not competitive content. It complements `scrape_videos` which tracks *other people's* videos.

## Running workers in dev

```bash
# Via Makefile — reads ENCRYPTION_KEY automatically, passes max_age_hours=0 (force-process all)
make worker-creators   # → POST /workers/scrape-creators
make worker-videos     # → POST /workers/scrape-videos
make worker-discover   # → POST /workers/discover-trends
make worker-publish    # → POST /workers/publish-scheduled (max_posts=10)
make worker-analytics  # → POST /workers/collect-analytics

# Manual curl (equivalent)
TOKEN=$(python -c "from app.config import settings; print(settings.ENCRYPTION_KEY)")
curl -X POST "http://localhost:8000/api/v1/workers/scrape-creators?max_age_hours=0" \
  -H "X-Dev-Worker-Token: $TOKEN"
```

## Production QStash setup

In the Upstash QStash dashboard, create schedules:

| Worker | Schedule | URL | Timeout |
|---|---|---|---|
| scrape-creators | `0 6 * * *` (daily 6 AM UTC) | `https://api.cliplift.com/api/v1/workers/scrape-creators` | 120s |
| scrape-videos | `0 */6 * * *` (every 6h) | `https://api.cliplift.com/api/v1/workers/scrape-videos` | 120s |
| discover-trends | `0 * * * *` (every hour) | `https://api.cliplift.com/api/v1/workers/discover-trends` | 120s |
| publish-scheduled | `*/5 * * * *` (every 5 min) | `https://api.cliplift.com/api/v1/workers/publish-scheduled` | 120s |
| collect-analytics | `0 7 * * *` (daily 7 AM UTC) | `https://api.cliplift.com/api/v1/workers/collect-analytics` | 120s |

Set the signing keys in `.env`:
```
QSTASH_CURRENT_SIGNING_KEY=sig_...
QSTASH_NEXT_SIGNING_KEY=sig_...    # for key rotation
```

## Error handling

- Workers always return 200 with a summary. Failures are reported in the response body, not as HTTP errors.
- QStash retries on non-200 responses. Since workers always return 200 (even on individual item failures), QStash doesn't retry.
- Individual item failures don't abort the batch — the worker continues to the next item.
- Failed publish posts get `status='failed'` with `error_message` — users see the error on the post detail page and can retry.
