# Publishing Pipeline

End-to-end documentation for the Cliplift publishing system: upload, schedule, OAuth, token refresh, and the publish worker.

---

## Table of Contents

1. [Upload Flow](#1-upload-flow)
2. [Storage Backends](#2-storage-backends)
3. [OAuth Flow](#3-oauth-flow)
4. [Publisher Abstraction](#4-publisher-abstraction)
5. [Token Refresh](#5-token-refresh)
6. [Publish Worker](#6-publish-worker)
7. [ScheduledPost Lifecycle](#7-scheduledpost-lifecycle)
8. [Status Guards](#8-status-guards)

---

## 1. Upload Flow

Video bytes never touch the FastAPI server. The browser uploads directly to storage via a presigned URL.

```
Browser                        FastAPI                      Storage (Supabase / Local)
  |                              |                              |
  |  POST /publishing/           |                              |
  |    uploads/presign           |                              |
  |  { filename, content_type }  |                              |
  |----------------------------->|                              |
  |                              |  create_upload_url(file_key) |
  |                              |----------------------------->|
  |                              |         signed URL           |
  |                              |<-----------------------------|
  |  { upload_url, file_key,     |                              |
  |    expires_at }              |                              |
  |<-----------------------------|                              |
  |                                                             |
  |  PUT <upload_url>                                           |
  |  [raw video bytes]                                          |
  |------------------------------------------------------------>|
  |                              204                            |
  |<------------------------------------------------------------|
  |                              |                              |
  |  POST /publishing/           |                              |
  |    scheduled-posts           |                              |
  |  { file_key, ... }           |                              |
  |----------------------------->|                              |
  |                              |  (stores file_key on row)    |
  |  201 ScheduledPostResponse   |                              |
  |<-----------------------------|                              |
```

### Presign details

- **Endpoint**: `POST /api/v1/publishing/uploads/presign`
- **Rate limit**: 20 requests / hour per user
- **Billing gate**: `require_active_plan` + `enforce_scheduling_enabled`
- **Allowed MIME types**: `video/mp4`, `video/quicktime`, `video/webm`, `video/x-m4v`
- **file_key format**: `{team_id}/{random_uuid}/{filename}` -- team-namespaced, unguessable
- **Expiry**: 600 seconds (10 minutes)

### Local dev upload sink

When `STORAGE_BACKEND=local`, the presigned URL points back to the FastAPI server itself:

```
PUT /api/v1/publishing/uploads/local/{file_key}   -- writes to ./uploads/
GET /api/v1/publishing/uploads/local/{file_key}    -- reads from ./uploads/
```

These routes return 404 when the storage backend is `SupabaseStorageBackend`. The file_key embeds `<team_uuid>/<random_uuid>/` as an implicit auth token -- guessing both UUIDs is infeasible.

---

## 2. Storage Backends

### Protocol

All backends implement `StorageBackend` (a Python `Protocol`):

| Method | Purpose |
|---|---|
| `create_upload_url(file_key, content_type, expires_in)` | Presigned PUT URL for browser |
| `create_download_url(file_key, expires_in)` | Presigned GET URL (used by Instagram publisher) |
| `write_bytes(file_key, data, content_type)` | Direct write (tests, dev PUT sink) |
| `download_bytes(file_key)` | Read bytes (publish worker) |
| `delete(file_key)` | Idempotent delete |
| `exists(file_key)` | Check existence |

### Implementations

| Backend | Class | When used |
|---|---|---|
| Local disk | `LocalStorageBackend` | Dev, tests. Writes to `./uploads/` |
| Supabase Storage | `SupabaseStorageBackend` | Production. Uses service role key for server ops |

### Factory logic (`build_storage`)

The `STORAGE_BACKEND` setting controls selection:

| Value | Behavior |
|---|---|
| `local` | Always `LocalStorageBackend` |
| `supabase` | Always `SupabaseStorageBackend` (fails if `SUPABASE_SERVICE_ROLE_KEY` unset) |
| `auto` (default) | `SupabaseStorageBackend` if `ENVIRONMENT=production` AND `SUPABASE_SERVICE_ROLE_KEY` set; otherwise `LocalStorageBackend` |

The `auto` default keeps dev and tests on local disk even when the local Supabase stack is running.

### Key files

- `backend/app/common/storage.py` -- backend protocol + both implementations + factory

---

## 3. OAuth Flow

OAuth connects a user's YouTube/Instagram/LinkedIn account to their Cliplift team.

```
Browser                   FastAPI                  OAuth Provider (Google/Meta)
  |                         |                         |
  | POST /connections/      |                         |
  |   {platform}/authorize  |                         |
  |------------------------>|                         |
  |                         | generate_state()        |
  |                         | store_state(state,      |
  |                         |   {team_id, platform})  |
  |                         |                         |
  | { authorize_url, state }|                         |
  |<------------------------|                         |
  |                                                   |
  | GET <authorize_url>     (user visits consent)     |
  |-------------------------------------------------->|
  |              consent screen                       |
  |<--------------------------------------------------|
  |                                                   |
  | redirect to /connections/{platform}/callback      |
  |   ?code=AUTH_CODE&state=STATE                     |
  |------------------------>|                         |
  |                         | retrieve_state(state)   |
  |                         | validate platform match |
  |                         |                         |
  |                         | exchange_code(code)     |
  |                         |------------------------>|
  |                         | { access_token,         |
  |                         |   refresh_token,        |
  |                         |   expires_in, ... }     |
  |                         |<------------------------|
  |                         |                         |
  |                         | encrypt_token(access)   |
  |                         | encrypt_token(refresh)  |
  |                         | upsert PlatformConnection
  |                         |                         |
  | 302 -> /dashboard/settings/connections?connected=1|
  |<------------------------|                         |
```

### Key behaviors

- **State token**: Random UUID, stored server-side (in-memory or Redis). Binds `team_id` + `platform` to the request. Validated on callback.
- **Callback has no JWT auth**: The browser is redirected from Google/Meta, not sending an Authorization header. The state token is the auth mechanism.
- **Idempotent upsert**: One connection per `(team_id, platform, platform_user_id)`. Reconnecting updates tokens, does not create duplicates.
- **Tokens encrypted at rest**: AES-256 via Fernet (`app/common/encryption.py`). The DB column holds ciphertext. Tokens are decrypted only in-memory at publish time.
- **Billing enforcement**: `require_active_plan` + `enforce_platform_connection_limit` on the authorize endpoint.

### OAuth providers

| Platform | Real provider | Mock fallback | Env vars required |
|---|---|---|---|
| YouTube | `YouTubeOAuthProvider` (Google OAuth 2.0) | `MockOAuthProvider` | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` |
| Instagram | `InstagramOAuthProvider` (Meta Graph API) | `MockOAuthProvider` | `META_OAUTH_CLIENT_ID`, `META_OAUTH_CLIENT_SECRET` |
| LinkedIn | -- (Phase 3) | `MockOAuthProvider` | -- |
| TikTok | -- (Phase 2) | `MockOAuthProvider` | -- |

### Mock OAuth flow

When env vars are missing, `MockOAuthProvider` returns a self-callback URL as the authorize URL. The browser visits it, which immediately completes the flow with deterministic fake tokens. The full flow works end-to-end without any external API calls.

### Key files

- `backend/app/publishing/oauth_routes.py` -- HTTP endpoints
- `backend/app/publishing/oauth_service.py` -- orchestration (start_authorize, complete_callback)
- `backend/app/publishing/oauth_providers/base.py` -- `OAuthProvider` ABC, `TokenExchangeResult`
- `backend/app/publishing/oauth_providers/youtube.py` -- Google OAuth 2.0
- `backend/app/publishing/oauth_providers/instagram.py` -- Meta Graph API
- `backend/app/publishing/oauth_providers/mock.py` -- deterministic mock
- `backend/app/publishing/oauth_factory.py` -- picks real vs mock per platform
- `backend/app/publishing/oauth_state.py` -- state token generation + storage

---

## 4. Publisher Abstraction

The publisher layer is the write-side mirror of `DataProviderRouter` (read-side). Same shape: ABC + concrete implementations + factory + router.

### Publisher ABC

```python
class Publisher(ABC):
    platform: Platform
    name: str

    async def publish(
        self, *, db, connection, post, video_bytes, video_url
    ) -> PublishResult: ...
```

The worker passes both `video_bytes` (raw file content) and `video_url` (presigned download URL). Each publisher uses whichever the platform API requires.

### PublishResult

```python
class PublishResult(BaseModel):
    platform_post_id: str     # e.g., YouTube video ID
    published_url: str        # e.g., https://youtube.com/shorts/{id}
    published_at: datetime
```

### Implementations

| Publisher | Platform | API | Uses |
|---|---|---|---|
| `YouTubeShortsPublisher` | YouTube | Data API v3 `videos.insert` (multipart/related) | `video_bytes` |
| `InstagramReelsPublisher` | Instagram | Graph API container flow (3 steps) | `video_url` |
| `MockPublisher` | Any | No-op, returns deterministic fake IDs | Neither |

### YouTubeShortsPublisher

- Hand-rolls the `multipart/related` body (no `google-api-python-client` dependency)
- Sets category 22 ("People & Blogs"), privacy "public", `selfDeclaredMadeForKids=false`
- Title truncated to 100 chars (YouTube Shorts limit)
- 120s timeout on the upload POST

### InstagramReelsPublisher

Three-step container flow:

```
1. POST /{ig-user-id}/media      -> container_id
       (media_type=REELS, video_url, caption)

2. GET  /{container_id}?fields=status_code    (poll)
       IN_PROGRESS -> FINISHED | ERROR
       Poll every 5s, timeout 90s

3. POST /{ig-user-id}/media_publish           -> post_id
       (creation_id=container_id)
```

Instagram fetches the video from `video_url` (a presigned Supabase download URL with 1-hour expiry). `video_bytes` is ignored.

### PublisherRouter

Registry that maps `Platform -> Publisher`. The publish worker calls:

```python
publisher = publisher_router.get(Platform.YOUTUBE)
result = await publisher.publish(db=db, connection=conn, post=post, ...)
```

### Factory (`build_publisher_router`)

Checks whether each platform's OAuth provider is real or mocked:
- Real OAuth provider -> real publisher (can actually call the platform API)
- Mock OAuth provider -> `MockPublisher` (mock tokens would just 401 against real APIs)

Current state:

| Platform | Production | Dev/Test |
|---|---|---|
| YouTube | `YouTubeShortsPublisher` | `MockPublisher` |
| Instagram | `InstagramReelsPublisher` | `MockPublisher` |
| LinkedIn | `MockPublisher` | `MockPublisher` |
| TikTok | `MockPublisher` | `MockPublisher` |

### Key files

- `backend/app/publishing/publishers/base.py` -- `Publisher` ABC, `PublishResult`, `PublisherError`
- `backend/app/publishing/publishers/youtube.py` -- YouTube Data API v3
- `backend/app/publishing/publishers/instagram.py` -- Meta Graph API container flow
- `backend/app/publishing/publishers/mock.py` -- deterministic mock
- `backend/app/publishing/publishers/factory.py` -- `build_publisher_router()`
- `backend/app/publishing/publisher_router.py` -- `PublisherRouter` registry

---

## 5. Token Refresh

`_credentials.py:get_fresh_access_token` is called by every real publisher immediately before making API calls.

```
Publisher.publish()
  |
  v
get_fresh_access_token(db, connection, oauth_provider)
  |
  |-- Is token_expires_at > now + 5min?
  |     YES -> decrypt access_token, return it
  |     NO  -> continue to refresh
  |
  |-- Has refresh_token?
  |     NO  -> raise PublisherError("user must reconnect")
  |     YES -> continue
  |
  |-- decrypt refresh_token
  |-- oauth_provider.refresh_access_token(plaintext_refresh)
  |-- encrypt new access_token + refresh_token (if rotated)
  |-- update connection.token_expires_at
  |-- db.commit()
  |-- return plaintext access_token
```

### Safety margin

Tokens are refreshed **5 minutes before** actual expiry (`REFRESH_SAFETY_MARGIN = timedelta(minutes=5)`). This prevents the token from expiring mid-API-call (YouTube uploads can take 2+ minutes).

### Platform-specific refresh behavior

| Platform | Refresh mechanism | Token rotation |
|---|---|---|
| Google (YouTube) | Standard `grant_type=refresh_token` | May rotate refresh token |
| Meta (Instagram) | `grant_type=fb_exchange_token` with current access token | No refresh token; long-lived access tokens (60 days) are exchanged for new ones |

### Security invariant

The plaintext token exists only in the publisher's in-memory call stack. It is never logged, never returned via the API, and never stored in the DB unencrypted.

### Key file

- `backend/app/publishing/publishers/_credentials.py`

---

## 6. Publish Worker

The worker is a QStash-triggered HTTP endpoint, not a background process. QStash POSTs to `POST /api/v1/workers/publish-scheduled` on a 5-minute cron.

### Concurrency model

```
Step 1: Pick + Lock
  SELECT scheduled_posts
    WHERE status = 'scheduled'
      AND scheduled_for <= now()
    ORDER BY scheduled_for ASC
    LIMIT {max_posts}
    FOR UPDATE SKIP LOCKED
  -> flip status to 'publishing'
  -> COMMIT (releases row locks)

Step 2: Process each post (per-post try/except)
  for post_id in claimed_posts:
    try:
      _publish_one(post_id)
        |-- resolve Publisher from router
        |-- load PlatformConnection
        |-- storage.download_bytes(file_key)
        |-- storage.create_download_url(file_key, expires_in=3600)
        |-- publisher.publish(...)
        |-- post.status = 'published'
        |-- post.platform_post_id = result.platform_post_id
        |-- post.media_url = result.published_url
        |-- post.published_at = result.published_at
        |-- COMMIT
    except:
      ROLLBACK
      _mark_failed(post_id, error_message)
        |-- post.status = 'failed'
        |-- post.error_message = str(error)[:1000]
        |-- COMMIT
```

### Key design decisions

- **`SELECT FOR UPDATE SKIP LOCKED`**: Multiple concurrent worker instances never double-pick the same post. The status flip to `publishing` + commit happens atomically before processing begins.
- **Per-post try/except**: One failing post does not abort the batch. Partial success is better than total failure.
- **Rollback + re-fetch on failure**: After an exception, the session is rolled back and the post is re-fetched in a clean transaction before marking it `failed`.
- **`max_posts=1` default**: Conservative default. Can be tuned up for higher throughput.
- **Always returns 200**: The worker endpoint never raises. Failures are reported in the response body so QStash does not retry the entire batch.

### Key file

- `backend/app/workers/publish_scheduled.py`

---

## 7. ScheduledPost Lifecycle

```
                          +-------+
             create       |       |     PATCH status=scheduled
   (future scheduled_for) | draft |<--------------------------+
                          |       |----+                      |
                          +---+---+    |                      |
                              |        | PATCH status=scheduled
                              |        |                      |
              create          v        |                      |
   (past scheduled_for)  +-----------+ |                      |
          +------------->| scheduled |-+                      |
                         +-----------+                        |
                              |                               |
                              | worker picks up               |
                              | (SELECT FOR UPDATE            |
                              |  SKIP LOCKED)                 |
                              v                               |
                        +------------+                        |
                        | publishing |                        |
                        +-----+------+                        |
                              |                               |
                   +----------+----------+                    |
                   |                     |                    |
                   v                     v                    |
             +-----------+         +--------+                 |
             | published |         | failed |  PATCH ----------+
             +-----------+         +--------+  status=scheduled
                                               or status=draft
```

### Initial status on creation

- `scheduled_for` is in the future -> status starts as `scheduled`
- `scheduled_for` is in the past -> status starts as `draft` (won't be picked up by worker)

### Status transitions

| From | To | Trigger |
|---|---|---|
| `draft` | `scheduled` | User PATCH (`status=scheduled`) |
| `scheduled` | `draft` | User PATCH (`status=draft`) |
| `scheduled` | `publishing` | Worker picks up the post |
| `publishing` | `published` | Worker completes successfully |
| `publishing` | `failed` | Worker catches an exception |
| `failed` | `scheduled` | User PATCH (`status=scheduled`) |
| `failed` | `draft` | User PATCH (`status=draft`) |

---

## 8. Status Guards

### Editable vs locked states

| Status | Editable (PATCH/DELETE) | Reason |
|---|---|---|
| `draft` | Yes | Not yet queued |
| `scheduled` | Yes | Queued but not picked up |
| `failed` | Yes | Can retry or edit and reschedule |
| `publishing` | **No** | Worker is actively processing |
| `published` | **No** | Already live on the platform |

Attempting to PATCH a `publishing` or `published` post returns `409 Conflict`.

### Locked fields on update

These fields are set at creation and cannot be changed via PATCH:
- `connection_id`
- `platform`
- `file_key`

To change any of these, delete the post and create a new one.

### Allowed client-side status transitions

| Current status | Can transition to |
|---|---|
| `draft` | `scheduled` |
| `scheduled` | `draft` |
| `failed` | `scheduled`, `draft` |
| `publishing` | (none -- locked) |
| `published` | (none -- locked) |

Worker-driven transitions (`scheduled -> publishing -> published/failed`) are not exposed through the API. They happen exclusively in the publish worker.

---

## API Endpoint Summary

### Publishing (`/api/v1/publishing/`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/uploads/presign` | JWT + active plan | Generate presigned upload URL |
| `POST` | `/scheduled-posts` | JWT + active plan | Create a scheduled post |
| `GET` | `/scheduled-posts` | JWT | List posts (cursor-paginated, optional `?status=` filter) |
| `GET` | `/scheduled-posts/{id}` | JWT | Get single post |
| `PATCH` | `/scheduled-posts/{id}` | JWT + active plan | Update post (editable states only) |
| `DELETE` | `/scheduled-posts/{id}` | JWT | Delete post + best-effort file cleanup |
| `PUT` | `/uploads/local/{file_key}` | (dev only) | Local storage upload sink |
| `GET` | `/uploads/local/{file_key}` | (dev only) | Local storage download sink |

### Connections (`/api/v1/connections/`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | JWT | List connected platform accounts |
| `POST` | `/{platform}/authorize` | JWT + active plan | Start OAuth flow |
| `GET` | `/{platform}/callback` | State token | Complete OAuth callback |
| `DELETE` | `/{connection_id}` | JWT | Disconnect a platform account |

### Workers (`/api/v1/workers/`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/publish-scheduled` | QStash signature | Publish due scheduled posts |

---

## Data Models

### PlatformConnection

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `team_id` | UUID | FK -> teams |
| `platform` | String(32) | youtube, instagram, linkedin, tiktok |
| `platform_user_id` | String(255) | Provider's user ID |
| `platform_username` | String(255) | Display name / email |
| `access_token` | Text | **Fernet-encrypted ciphertext** |
| `refresh_token` | Text | **Fernet-encrypted ciphertext** |
| `token_expires_at` | DateTime(tz) | When access_token expires |
| `scopes` | ARRAY(String) | Granted OAuth scopes |
| `connected_at` | DateTime(tz) | Last connection/reconnection time |

### ScheduledPost

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `team_id` | UUID | FK -> teams |
| `connection_id` | UUID | FK -> platform_connections |
| `created_by` | UUID | FK -> profiles (audit trail) |
| `inspired_by_video_id` | UUID | FK -> videos (insight -> action link) |
| `platform` | String(32) | |
| `title` | String(512) | |
| `description` | Text | |
| `hashtags` | ARRAY(String) | |
| `file_key` | String(512) | Storage object key |
| `media_url` | String(1024) | Public URL, set after publish |
| `scheduled_for` | DateTime(tz) | When to publish |
| `status` | String(32) | draft / scheduled / publishing / published / failed |
| `platform_post_id` | String(255) | Set after successful publish |
| `error_message` | Text | Set on failure |
| `published_at` | DateTime(tz) | Set after successful publish |

### PostAnalytics

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `post_id` | UUID | FK -> scheduled_posts |
| `views` | BigInteger | |
| `likes` | BigInteger | |
| `comments` | BigInteger | |
| `shares` | BigInteger | |
| `watch_time_seconds` | BigInteger | |
| `avg_view_duration` | Float | |
| `snapshot_at` | DateTime(tz) | When this snapshot was taken |
| `raw_data` | JSONB | Full provider response |
