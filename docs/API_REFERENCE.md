# Cliplift API Reference

Backend REST API served by FastAPI at `/api/v1`. All requests and responses use JSON. Authenticated endpoints require a Supabase JWT in the `Authorization: Bearer <token>` header.

**Base URL:** `http://localhost:8000/api/v1` (dev) or `https://api.cliplift.com/api/v1` (prod)

---

## Table of Contents

- [Common Conventions](#common-conventions)
- [Auth](#auth) -- `/profile`, `/teams/me`
- [Creators](#creators) -- `/creators`
- [Videos](#videos) -- `/videos`
- [Discovery](#discovery) -- `/discover`
- [Niches](#niches) -- `/niches`
- [Analytics](#analytics) -- `/analytics`
- [Publishing](#publishing) -- `/publishing`
- [Connections (OAuth)](#connections-oauth) -- `/connections`
- [Billing](#billing) -- `/billing`
- [Workers](#workers) -- `/workers`

---

## Common Conventions

### Authentication

There are no register/login/logout endpoints. The frontend uses the Supabase Auth SDK directly. The backend validates the JWT and manages the application-level Profile row.

Three auth levels exist:

| Level | Description | Dependency |
|---|---|---|
| **None** | Public endpoint, no header needed | -- |
| **Auth** | Valid Supabase JWT required | `get_current_team` |
| **Active plan** | Auth + team must have active trial or subscription | `require_active_plan` |

### Pagination (cursor-based)

All list endpoints use cursor-based pagination. Pass these query parameters:

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` (1-100) | `20` | Max items per page |
| `cursor` | `string` | `null` | Opaque base64 cursor from the previous response's `next_cursor` |

Paginated responses always have this envelope:

```json
{
  "items": [ ... ],
  "next_cursor": "eyJ0Ijo...",
  "has_more": true
}
```

### Platform Enum

Used across many endpoints. Always a lowercase string.

| Value | Description |
|---|---|
| `youtube` | YouTube / YouTube Shorts |
| `instagram` | Instagram Reels |
| `linkedin` | LinkedIn video |
| `tiktok` | TikTok |

### Error Responses

All errors follow the standard FastAPI shape:

```json
{
  "detail": "Human-readable error message"
}
```

Common HTTP status codes:

| Code | Meaning |
|---|---|
| `401` | Missing or invalid JWT |
| `402` | Plan limit reached (upgrade required) |
| `403` | Cross-team access denied |
| `404` | Resource not found |
| `422` | Validation error (bad input) |
| `429` | Rate limit exceeded |

---

## Auth

Profile and team management. No register/login -- Supabase handles that.

### GET /profile

Get the current user's profile.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Response** `200 OK` -- `ProfileResponse`

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Profile ID (matches Supabase `auth.users.id`) |
| `email` | `string` | User's email |
| `name` | `string \| null` | Display name |
| `avatar_url` | `string \| null` | Avatar URL |
| `stripe_customer_id` | `string \| null` | Stripe customer ID |
| `created_at` | `datetime` | Account creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |

---

### PUT /profile

Update the current user's profile (name, avatar).

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Request body** -- `ProfileUpdate`

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | `string \| null` | No | max 255 chars | Display name |
| `avatar_url` | `string \| null` | No | max 512 chars | Avatar URL |

**Response** `200 OK` -- `ProfileResponse` (same shape as GET /profile)

---

### GET /teams/me

Get the current user's team with plan and trial info.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Response** `200 OK` -- `TeamResponse`

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Team ID |
| `name` | `string` | Team name |
| `owner_id` | `uuid` | Profile ID of the team owner |
| `plan` | `string` | Current plan (`"creator"`, `"team"`, `"agency"`) |
| `stripe_customer_id` | `string \| null` | Stripe customer ID |
| `stripe_subscription_id` | `string \| null` | Stripe subscription ID |
| `trial_ends_at` | `datetime \| null` | Trial expiration timestamp |
| `created_at` | `datetime` | Team creation timestamp |
| `is_trial_active` | `bool` | Computed: trial is currently active |
| `is_trial_expired` | `bool` | Computed: trial expired and no subscription |

---

## Creators

Track, untrack, list, and inspect creators across platforms.

### GET /creators

List tracked creators for the current team. Cursor-paginated.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Query params** -- standard [pagination params](#pagination-cursor-based)

**Response** `200 OK` -- `PaginatedResponse[TrackedCreatorResponse]`

Each item in `items`:

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Tracking record ID |
| `creator` | `CreatorResponse` | Nested creator object (see below) |
| `tracked_at` | `datetime` | When the creator was tracked |
| `notes` | `string \| null` | User-supplied notes |
| `latest_followers` | `int \| null` | Most recent follower count from snapshots |

**`CreatorResponse` shape:**

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Creator ID |
| `platform` | `Platform` | `youtube`, `instagram`, `linkedin`, `tiktok` |
| `platform_id` | `string` | Platform-specific creator identifier |
| `username` | `string \| null` | Creator username |
| `display_name` | `string \| null` | Creator display name |
| `avatar_url` | `string \| null` | Avatar URL |
| `bio` | `string \| null` | Bio text |
| `is_active` | `bool` | Whether the creator is currently active |
| `last_scraped_at` | `datetime \| null` | Last time metrics were refreshed |
| `created_at` | `datetime` | Row creation timestamp |

---

### POST /creators/track

Add a creator to the team's tracking list. Returns 402 if the team's plan limit is reached.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | 20 requests / 60 seconds |

**Request body** -- `TrackCreatorRequest`

Provide either `(platform + platform_id)` or a recognizable `url`. Explicit fields take precedence.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `platform` | `Platform` | No* | -- | Target platform |
| `platform_id` | `string` | No* | max 255 chars | Platform-specific creator ID |
| `url` | `string` | No* | max 512 chars | Creator profile URL (auto-parsed) |
| `notes` | `string` | No | max 1000 chars | Notes about this creator |

*At least one of `(platform + platform_id)` or `url` must be provided.

Supported URL patterns: `youtube.com/@...`, `youtube.com/channel/...`, `tiktok.com/@...`, `instagram.com/...`, `linkedin.com/in/...`

**Response** `201 Created` -- `TrackedCreatorResponse`

**Errors:**

| Code | Cause |
|---|---|
| `402` | Team creator tracking limit reached |
| `422` | Neither explicit fields nor a parseable URL provided |

---

### DELETE /creators/{creator_id}/untrack

Remove a creator from the team's tracking list.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `creator_id` | `uuid` | Creator tracking ID |

**Response** `204 No Content`

---

### GET /creators/{creator_id}

Get creator detail with recent snapshots.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `creator_id` | `uuid` | Creator ID |

**Response** `200 OK` -- `CreatorDetailResponse`

| Field | Type | Description |
|---|---|---|
| `creator` | `CreatorResponse` | Full creator object |
| `tracking` | `TrackedCreatorResponse \| null` | Tracking record, if tracked by this team |
| `recent_snapshots` | `CreatorSnapshotResponse[]` | Historical metric snapshots |

**`CreatorSnapshotResponse` shape:**

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Snapshot ID |
| `creator_id` | `uuid` | Parent creator ID |
| `followers` | `int \| null` | Follower count at snapshot time |
| `total_videos` | `int \| null` | Total video count |
| `avg_views_30d` | `float \| null` | 30-day rolling average views |
| `avg_engagement_30d` | `float \| null` | 30-day rolling average engagement |
| `snapshot_date` | `date` | Date of the snapshot |

---

## Videos

Track, untrack, list, and inspect videos across platforms.

### GET /videos

List tracked videos for the current team. Cursor-paginated.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Query params** -- standard [pagination params](#pagination-cursor-based)

**Response** `200 OK` -- `PaginatedResponse[TrackedVideoResponse]`

Each item in `items`:

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Tracking record ID |
| `video` | `VideoResponse` | Nested video object (see below) |
| `tracked_at` | `datetime` | When the video was tracked |

**`VideoResponse` shape:**

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Video ID |
| `creator_id` | `uuid \| null` | Linked creator ID |
| `platform` | `Platform` | Platform enum value |
| `platform_video_id` | `string` | Platform-specific video identifier |
| `title` | `string \| null` | Video title |
| `description` | `string \| null` | Video description |
| `thumbnail_url` | `string \| null` | Thumbnail URL |
| `duration_seconds` | `int \| null` | Duration in seconds |
| `published_at` | `datetime \| null` | Original publish timestamp |
| `hashtags` | `string[] \| null` | Hashtags used |
| `is_short` | `bool` | Whether this is a short-form video |
| `outlier_score` | `float \| null` | Creator-relative outlier Z-score |
| `is_outlier` | `bool` | Whether the video exceeds the outlier threshold |
| `latest_views` | `int` | Most recent view count |
| `latest_likes` | `int` | Most recent like count |
| `latest_comments` | `int` | Most recent comment count |
| `latest_shares` | `int` | Most recent share count |
| `latest_engagement_rate` | `float \| null` | Most recent engagement rate |
| `latest_snapshot_at` | `datetime \| null` | Time of the most recent metric snapshot |
| `created_at` | `datetime` | Row creation timestamp |

---

### POST /videos/track

Add a video to the team's tracking list.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | 30 requests / 60 seconds |

**Request body** -- `TrackVideoRequest`

Provide either `(platform + platform_video_id)` or a recognizable `url`. Explicit fields take precedence.

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `platform` | `Platform` | No* | -- | Target platform |
| `platform_video_id` | `string` | No* | max 255 chars | Platform-specific video ID |
| `url` | `string` | No* | max 512 chars | Video URL (auto-parsed) |

*At least one of `(platform + platform_video_id)` or `url` must be provided.

Supported URL patterns: `youtube.com/shorts/...`, `youtube.com/watch?v=...`, `youtu.be/...`, `tiktok.com/.../video/...`, `instagram.com/reel/...`, `instagram.com/p/...`, `linkedin.com/.../...`

**Response** `201 Created` -- `TrackedVideoResponse`

**Errors:**

| Code | Cause |
|---|---|
| `422` | Neither explicit fields nor a parseable URL provided |

---

### DELETE /videos/{video_id}/untrack

Remove a video from the team's tracking list.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `video_id` | `uuid` | Video tracking ID |

**Response** `204 No Content`

---

### GET /videos/{video_id}

Get video detail with recent snapshots.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `video_id` | `uuid` | Video ID |

**Response** `200 OK` -- `VideoDetailResponse`

| Field | Type | Description |
|---|---|---|
| `video` | `VideoResponse` | Full video object |
| `tracking` | `TrackedVideoResponse \| null` | Tracking record, if tracked by this team |
| `recent_snapshots` | `VideoSnapshotResponse[]` | Historical metric snapshots |

**`VideoSnapshotResponse` shape:**

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Snapshot ID |
| `video_id` | `uuid` | Parent video ID |
| `views` | `int \| null` | View count |
| `likes` | `int \| null` | Like count |
| `comments` | `int \| null` | Comment count |
| `shares` | `int \| null` | Share count |
| `engagement_rate` | `float \| null` | Engagement rate |
| `view_velocity` | `float \| null` | Views per hour since last snapshot |
| `snapshot_at` | `datetime` | Snapshot timestamp |

---

## Discovery

Public trend search and authenticated AI content brief generation.

### POST /discover/search

Search trending videos across platforms. PUBLIC -- no authentication required.

Searches the requested platforms in parallel, applies Z-score outlier detection per platform, and returns videos sorted by outlier status + views.

| | |
|---|---|
| **Auth** | None (public) |
| **Rate limit** | 30 requests / 60 seconds per IP |

**Request body** -- `SearchRequest`

| Field | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `query` | `string` | Yes | -- | 1-200 chars | Search keywords |
| `platforms` | `Platform[]` | No | all four | 1-4 items | Which platforms to search |
| `limit_per_platform` | `int` | No | `20` | 1-50 | Max results per platform |
| `outlier_threshold` | `float` | No | `3.0` | 1.0-5.0 | Z-score threshold for outlier flag |

**Response** `200 OK` -- `SearchResponse`

| Field | Type | Description |
|---|---|---|
| `query` | `string` | Echo of the search query |
| `total` | `int` | Total number of results |
| `outlier_count` | `int` | Number of results flagged as outliers |
| `by_platform` | `PlatformResultSummary[]` | Per-platform breakdown |
| `videos` | `VideoSearchResult[]` | Sorted results |

**`PlatformResultSummary` shape:**

| Field | Type | Description |
|---|---|---|
| `platform` | `Platform` | Platform name |
| `count` | `int` | Number of results from this platform |
| `outlier_count` | `int` | Number of outliers from this platform |

**`VideoSearchResult` shape:**

| Field | Type | Description |
|---|---|---|
| `platform` | `Platform` | Source platform |
| `platform_video_id` | `string` | Platform-specific video ID |
| `url` | `string` | Direct URL to the video |
| `title` | `string` | Video title |
| `description` | `string \| null` | Video description |
| `creator_username` | `string` | Creator's username |
| `creator_display_name` | `string \| null` | Creator's display name |
| `creator_platform_id` | `string \| null` | Creator's platform ID |
| `creator_followers` | `int \| null` | Creator's follower count |
| `views` | `int` | View count |
| `likes` | `int` | Like count |
| `comments` | `int` | Comment count |
| `shares` | `int` | Share count |
| `engagement_rate` | `float \| null` | Engagement rate |
| `published_at` | `datetime \| null` | Publish timestamp |
| `thumbnail_url` | `string \| null` | Thumbnail URL |
| `duration_seconds` | `int \| null` | Duration in seconds |
| `hashtags` | `string[]` | Hashtags |
| `outlier_score` | `float \| null` | Z-score (filled by outlier detection) |
| `is_outlier` | `bool` | Whether this video exceeds the threshold |

---

### GET /discover/providers

Returns a map of platform to provider name. Useful for debugging mock vs live mode.

| | |
|---|---|
| **Auth** | None (public) |
| **Rate limit** | None |

**Response** `200 OK` -- `dict[string, string]`

```json
{
  "youtube": "mock",
  "instagram": "mock",
  "linkedin": "netrows",
  "tiktok": "data365"
}
```

---

### POST /discover/generate-idea

Generate an AI content brief from a tracked video. Analyzes the video and returns a structured brief with hook analysis, format, suggested caption, hashtags, and CTA. Cached per `video_id` for 7 days.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | 10 requests / hour per user |

**Request body** -- `GenerateIdeaRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `video_id` | `uuid` | Yes | ID of the video to generate a brief from |

**Response** `200 OK` -- `GenerateIdeaResponse`

| Field | Type | Description |
|---|---|---|
| `video_id` | `uuid` | Echo of the input video ID |
| `brief` | `ContentBrief` | Structured AI-generated content brief |

**`ContentBrief` shape:**

| Field | Type | Description |
|---|---|---|
| `hook_analysis` | `string` | Why the original hook works (1-2 sentences) |
| `format` | `string` | Video format description, e.g. "talking head + b-roll cuts" |
| `suggested_hook` | `string` | Your version of the hook (1 sentence) |
| `suggested_caption` | `string` | Full caption ready to post (2-3 sentences) |
| `suggested_hashtags` | `string[]` | 5-8 relevant hashtags |
| `cta` | `string` | Call to action for the viewer (1 sentence) |
| `generated_at` | `datetime` | When the brief was generated |
| `cached` | `bool` | Whether this brief was served from cache |

**Errors:**

| Code | Cause |
|---|---|
| `404` | Video not found |
| `429` | Rate limit exceeded (10/hour) |

---

## Niches

CRUD for user-defined keyword groups. Niches drive the auto-discovery worker, which searches across platforms and populates the niche feed with outlier videos.

### GET /niches

List the team's niches. Cursor-paginated.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Query params** -- standard [pagination params](#pagination-cursor-based)

**Response** `200 OK` -- `PaginatedResponse[NicheResponse]`

**`NicheResponse` shape:**

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Niche ID |
| `team_id` | `uuid` | Owning team ID |
| `name` | `string` | Niche name |
| `keywords` | `string[]` | Search terms (1-20) |
| `platforms` | `Platform[]` | Target platforms |
| `is_active` | `bool` | Whether the worker should process this niche |
| `last_analyzed_at` | `datetime \| null` | Last worker run timestamp |
| `created_at` | `datetime` | Creation timestamp |

---

### POST /niches

Create a new niche.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | None |

**Request body** -- `NicheCreate`

| Field | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `name` | `string` | Yes | -- | 1-255 chars | Niche name |
| `keywords` | `string[]` | Yes | -- | 1-20 items | Search terms |
| `platforms` | `Platform[]` | No | all four | 1-4 items | Target platforms |
| `is_active` | `bool` | No | `true` | -- | Whether to auto-discover |

**Response** `201 Created` -- `NicheResponse`

---

### GET /niches/{niche_id}

Get a single niche.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `niche_id` | `uuid` | Niche ID |

**Response** `200 OK` -- `NicheResponse`

---

### PUT /niches/{niche_id}

Update a niche. All fields are optional.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `niche_id` | `uuid` | Niche ID |

**Request body** -- `NicheUpdate`

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | `string` | No | 1-255 chars | Niche name |
| `keywords` | `string[]` | No | 1-20 items | Search terms |
| `platforms` | `Platform[]` | No | 1-4 items | Target platforms |
| `is_active` | `bool` | No | -- | Whether to auto-discover |

**Response** `200 OK` -- `NicheResponse`

---

### DELETE /niches/{niche_id}

Delete a niche.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `niche_id` | `uuid` | Niche ID |

**Response** `204 No Content`

---

### GET /niches/{niche_id}/feed

Get auto-discovered videos for a niche, sorted by `discovered_at` (newest first). Empty until the discover-trends worker has run.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `niche_id` | `uuid` | Niche ID |

**Query params** -- standard [pagination params](#pagination-cursor-based)

**Response** `200 OK` -- `PaginatedResponse[NicheFeedItem]`

**`NicheFeedItem` shape:**

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Niche-video join table ID |
| `niche_id` | `uuid` | Parent niche ID |
| `discovered_at` | `datetime` | When this video was discovered for this niche |
| `niche_outlier_score` | `float \| null` | Niche-relative outlier Z-score (separate from creator-relative score on `VideoResponse`) |
| `video` | `VideoResponse` | Full video object |

---

## Analytics

Dashboard metrics and detail-page timelines. All endpoints are auth-required and team-scoped. Results are cached for 5 minutes.

### GET /analytics/overview

Dashboard overview stats for the current team.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |
| **Cache** | 5 minutes (bypass with `fresh=true`) |

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `fresh` | `bool` | `false` | Bypass cache and recompute |

**Response** `200 OK` -- `OverviewResponse`

| Field | Type | Description |
|---|---|---|
| `tracked_creators` | `int` | Number of tracked creators |
| `tracked_videos` | `int` | Number of tracked videos |
| `active_niches` | `int` | Number of active niches |
| `total_outliers` | `int` | Total outlier videos across niches |
| `recent_snapshots_24h` | `int` | Snapshots taken in the last 24 hours |

---

### GET /analytics/creators/{creator_id}/timeline

Creator snapshot timeline for charts. Returns daily data points.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |
| **Cache** | 5 minutes |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `creator_id` | `uuid` | Creator ID |

**Query params:**

| Param | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `days` | `int` | `30` | 1-365 | Number of days of history |

**Response** `200 OK` -- `CreatorTimelineResponse`

| Field | Type | Description |
|---|---|---|
| `creator_id` | `uuid` | Creator ID |
| `days` | `int` | Echo of the requested day count |
| `points` | `CreatorTimelinePoint[]` | Timeline data points |

**`CreatorTimelinePoint` shape:**

| Field | Type | Description |
|---|---|---|
| `snapshot_date` | `date` | Date of the data point |
| `followers` | `int \| null` | Follower count |
| `total_videos` | `int \| null` | Total videos |
| `avg_views_30d` | `float \| null` | 30-day rolling average views |
| `avg_engagement_30d` | `float \| null` | 30-day rolling average engagement |

---

### GET /analytics/videos/{video_id}/timeline

Video snapshot timeline for velocity curves. Returns hourly data points.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |
| **Cache** | 5 minutes |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `video_id` | `uuid` | Video ID |

**Query params:**

| Param | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `hours` | `int` | `72` | 1-720 | Number of hours of history |

**Response** `200 OK` -- `VideoTimelineResponse`

| Field | Type | Description |
|---|---|---|
| `video_id` | `uuid` | Video ID |
| `hours` | `int` | Echo of the requested hour count |
| `points` | `VideoTimelinePoint[]` | Timeline data points |

**`VideoTimelinePoint` shape:**

| Field | Type | Description |
|---|---|---|
| `snapshot_at` | `datetime` | Snapshot timestamp |
| `views` | `int \| null` | View count |
| `likes` | `int \| null` | Like count |
| `comments` | `int \| null` | Comment count |
| `engagement_rate` | `float \| null` | Engagement rate |
| `view_velocity` | `float \| null` | Views per hour since last snapshot |

---

### GET /analytics/niches/{niche_id}/performance

Niche performance breakdown: platform stats and daily discovery counts.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |
| **Cache** | 5 minutes |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `niche_id` | `uuid` | Niche ID |

**Query params:**

| Param | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `days` | `int` | `30` | 1-365 | Number of days of history |

**Response** `200 OK` -- `NichePerformanceResponse`

| Field | Type | Description |
|---|---|---|
| `niche_id` | `uuid` | Niche ID |
| `days` | `int` | Echo of the requested day count |
| `total_videos` | `int` | Total videos discovered in this niche |
| `total_outliers` | `int` | Total outliers discovered |
| `platform_breakdown` | `NichePlatformBreakdown[]` | Counts per platform |
| `daily` | `NichePerformanceDay[]` | Daily discovery + outlier counts |

**`NichePlatformBreakdown` shape:**

| Field | Type | Description |
|---|---|---|
| `platform` | `string` | Platform name |
| `count` | `int` | Number of videos from this platform |

**`NichePerformanceDay` shape:**

| Field | Type | Description |
|---|---|---|
| `day` | `date` | Calendar date |
| `videos_discovered` | `int` | Videos discovered on this day |
| `outliers` | `int` | Outliers discovered on this day |

---

### GET /analytics/recent-outliers

Top recent outliers across the team's niches.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |
| **Cache** | 5 minutes |

**Query params:**

| Param | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `limit` | `int` | `10` | 1-50 | Max outliers to return |

**Response** `200 OK` -- `RecentOutliersResponse`

| Field | Type | Description |
|---|---|---|
| `items` | `RecentOutlier[]` | Outlier list |
| `total` | `int` | Total count |

**`RecentOutlier` shape:**

| Field | Type | Description |
|---|---|---|
| `niche_video_id` | `uuid` | Niche-video join table ID |
| `niche_id` | `uuid` | Source niche ID |
| `niche_name` | `string` | Niche name (denormalized) |
| `outlier_score` | `float` | Z-score |
| `discovered_at` | `datetime` | Discovery timestamp |
| `video_id` | `uuid` | Video ID |
| `platform` | `Platform` | Platform |
| `title` | `string \| null` | Video title |
| `thumbnail_url` | `string \| null` | Thumbnail |
| `views` | `int` | View count |
| `likes` | `int` | Like count |
| `engagement_rate` | `float \| null` | Engagement rate |

---

## Publishing

Presigned uploads and scheduled post CRUD.

### POST /publishing/uploads/presign

Generate a presigned upload URL for a video file. The browser PUTs the file directly to the returned URL -- the file never touches the FastAPI server. The returned `file_key` is what you pass to `POST /publishing/scheduled-posts` to attach the uploaded file.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | 20 requests / hour |

**Request body** -- `PresignRequest`

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `filename` | `string` | Yes | 1-255 chars, no path separators, no leading dot | Video filename |
| `content_type` | `string` | Yes | One of: `video/mp4`, `video/quicktime`, `video/webm`, `video/x-m4v` | MIME type |

**Response** `200 OK` -- `PresignResponse`

| Field | Type | Description |
|---|---|---|
| `upload_url` | `string` | Presigned URL to PUT the file to |
| `file_key` | `string` | Opaque key to reference this upload in scheduled posts |
| `expires_at` | `datetime` | When the upload URL expires |

---

### POST /publishing/scheduled-posts

Create a scheduled post.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | None |

**Request body** -- `ScheduledPostCreate`

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `connection_id` | `uuid` | Yes | -- | Platform connection to publish through |
| `platform` | `Platform` | Yes | -- | Target platform |
| `file_key` | `string` | Yes | 1-512 chars | File key from presign endpoint |
| `title` | `string` | No | max 512 chars | Post title |
| `description` | `string` | No | -- | Post description/caption |
| `hashtags` | `string[]` | No | max 30 items | Hashtags |
| `scheduled_for` | `datetime` | Yes | -- | When to publish |
| `inspired_by_video_id` | `uuid` | No | -- | Link back to the inspiring video |

**Response** `201 Created` -- `ScheduledPostResponse`

---

### GET /publishing/scheduled-posts

List the team's scheduled posts. Cursor-paginated.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` | `20` | Max items per page (1-100) |
| `cursor` | `string` | `null` | Pagination cursor |
| `status` | `PostStatus` | `null` | Filter by status: `draft`, `scheduled`, `publishing`, `published`, `failed` |

**Response** `200 OK` -- `PaginatedResponse[ScheduledPostResponse]`

---

### GET /publishing/scheduled-posts/{post_id}

Get a single scheduled post.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `post_id` | `uuid` | Post ID |

**Response** `200 OK` -- `ScheduledPostResponse`

---

### PATCH /publishing/scheduled-posts/{post_id}

Update a scheduled post. Only posts with status `draft`, `scheduled`, or `failed` are editable. `connection_id`, `platform`, and `file_key` are locked after creation -- delete and recreate to change them.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `post_id` | `uuid` | Post ID |

**Request body** -- `ScheduledPostUpdate`

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `title` | `string` | No | max 512 chars | Post title |
| `description` | `string` | No | -- | Post description/caption |
| `hashtags` | `string[]` | No | max 30 items | Hashtags |
| `scheduled_for` | `datetime` | No | -- | When to publish |
| `inspired_by_video_id` | `uuid` | No | -- | Link back to the inspiring video |
| `status` | `PostStatus` | No | -- | Change post status |

**Response** `200 OK` -- `ScheduledPostResponse`

---

### DELETE /publishing/scheduled-posts/{post_id}

Delete a scheduled post and its associated file.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `post_id` | `uuid` | Post ID |

**Response** `204 No Content`

---

### ScheduledPostResponse shape

Returned by all scheduled post endpoints.

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Post ID |
| `team_id` | `uuid` | Owning team ID |
| `connection_id` | `uuid` | Platform connection ID |
| `created_by` | `uuid \| null` | Profile ID of the creator |
| `inspired_by_video_id` | `uuid \| null` | Linked inspiring video |
| `platform` | `Platform` | Target platform |
| `title` | `string \| null` | Post title |
| `description` | `string \| null` | Post description/caption |
| `hashtags` | `string[] \| null` | Hashtags |
| `file_key` | `string \| null` | Upload file key |
| `media_url` | `string \| null` | Public URL after upload |
| `scheduled_for` | `datetime` | Scheduled publish time |
| `status` | `PostStatus` | Current status: `draft`, `scheduled`, `publishing`, `published`, `failed` |
| `platform_post_id` | `string \| null` | ID on the target platform after publishing |
| `error_message` | `string \| null` | Error details if status is `failed` |
| `published_at` | `datetime \| null` | Actual publish timestamp |
| `created_at` | `datetime` | Row creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |

---

### Dev-only: PUT /publishing/uploads/local/{file_key}

Upload sink for `LocalStorageBackend` in dev environments. In production this returns `404` because uploads go directly to Supabase Storage via presigned URLs. Not included in the OpenAPI schema (`include_in_schema=False`).

### Dev-only: GET /publishing/uploads/local/{file_key}

Download sink for `LocalStorageBackend` in dev environments. Returns `video/mp4` content. Not included in the OpenAPI schema.

---

## Connections (OAuth)

Manage platform OAuth connections for publishing.

### GET /connections

List connected platform accounts for the current team. Tokens are never returned -- only metadata.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Response** `200 OK` -- `ConnectionResponse[]`

| Field | Type | Description |
|---|---|---|
| `id` | `uuid` | Connection ID |
| `platform` | `Platform` | Connected platform |
| `platform_user_id` | `string \| null` | User's ID on the platform |
| `platform_username` | `string \| null` | User's username on the platform |
| `scopes` | `string[] \| null` | Granted OAuth scopes |
| `token_expires_at` | `datetime \| null` | Token expiration time |
| `connected_at` | `datetime` | When the connection was established |
| `is_expired` | `bool` | Whether the token has expired |

---

### POST /connections/{platform}/authorize

Begin the OAuth flow for a platform. Returns a URL for the user's browser to visit. After consent, the provider redirects back to the callback endpoint.

| | |
|---|---|
| **Auth** | Active plan required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `platform` | `Platform` | Target platform: `youtube`, `instagram`, `linkedin`, `tiktok` |

**Response** `200 OK` -- `AuthorizeResponse`

| Field | Type | Description |
|---|---|---|
| `authorize_url` | `string` | URL to redirect the user's browser to |
| `state` | `string` | CSRF state token |
| `platform` | `Platform` | Echo of the target platform |

**Errors:**

| Code | Cause |
|---|---|
| `402` | Platform connection limit reached for the team's plan |

---

### GET /connections/{platform}/callback

OAuth callback. Called by the OAuth provider after the user grants consent. Validates the state, exchanges the code for tokens, encrypts and persists them, then redirects the user to `/dashboard/settings/connections`.

This endpoint does NOT require a JWT -- the user is being redirected from the OAuth provider, not sending an API request. The `state` token authorizes the request.

| | |
|---|---|
| **Auth** | None (state token validates the request) |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `platform` | `Platform` | Platform that completed the OAuth flow |

**Query params:**

| Param | Type | Description |
|---|---|---|
| `code` | `string` | Authorization code from the OAuth provider |
| `state` | `string` | CSRF state token (must match the one from `/authorize`) |

**Response** `302 Found` -- Redirects to `{FRONTEND_URL}/dashboard/settings/connections?connected=1`

---

### DELETE /connections/{connection_id}

Disconnect a platform account.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Path params:**

| Param | Type | Description |
|---|---|---|
| `connection_id` | `uuid` | Connection ID |

**Response** `204 No Content`

---

## Billing

Stripe integration for checkout, customer portal, and webhook processing.

### POST /billing/checkout

Create a Stripe Checkout Session. Returns a URL to redirect the user to Stripe's hosted checkout page.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Request body** -- `CheckoutSessionRequest`

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `plan` | `string` | Yes | -- | One of: `creator`, `team`, `agency` |
| `billing_period` | `string` | No | `monthly` | One of: `monthly`, `annual` |

**Response** `200 OK` -- `CheckoutSessionResponse`

| Field | Type | Description |
|---|---|---|
| `checkout_url` | `string` | Stripe-hosted checkout URL |
| `session_id` | `string` | Stripe session ID |

---

### POST /billing/portal

Create a Stripe Billing Portal link for managing subscriptions.

| | |
|---|---|
| **Auth** | Required |
| **Rate limit** | None |

**Response** `200 OK` -- `BillingPortalResponse`

| Field | Type | Description |
|---|---|---|
| `portal_url` | `string` | Stripe-hosted billing portal URL |

---

### POST /billing/webhook

Stripe webhook receiver. No auth -- Stripe signs the request with the `Stripe-Signature` header, which is validated server-side.

| | |
|---|---|
| **Auth** | None (Stripe-signed) |
| **Rate limit** | None |

**Headers:**

| Header | Description |
|---|---|
| `Stripe-Signature` | Stripe webhook signature for payload verification |

**Request body** -- raw Stripe event payload (JSON)

**Response** `200 OK` -- `{"status": "ok"}`

---

## Workers

HTTP endpoints triggered by QStash on a cron schedule. All endpoints require a valid QStash signature (verified by middleware). These are not called by the frontend.

All worker endpoints accept an optional `max_age_hours` query parameter. Pass `max_age_hours=0` to force-process all rows regardless of `last_scraped_at` (useful for dev/testing).

### POST /workers/scrape-creators

Daily refresh of tracked creator metrics. Processes creators whose `last_scraped_at` is older than `max_age_hours`.

| | |
|---|---|
| **Auth** | QStash signature |
| **Schedule** | Daily |

**Query params:**

| Param | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `max_age_hours` | `int` | `24` | 0-720 | Skip creators scraped more recently than this |

**Response** `200 OK`

```json
{
  "processed": 42,
  "skipped": 8,
  "errors": 0
}
```

---

### POST /workers/scrape-videos

6-hourly refresh of tracked video metrics and view velocity. Processes videos whose `last_scraped_at` is older than `max_age_hours`.

| | |
|---|---|
| **Auth** | QStash signature |
| **Schedule** | Every 6 hours |

**Query params:**

| Param | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `max_age_hours` | `int` | `6` | 0-720 | Skip videos scraped more recently than this |

**Response** `200 OK` -- same shape as scrape-creators

---

### POST /workers/discover-trends

Hourly auto-discovery for all active niches. Searches each niche's keywords across its configured platforms, runs outlier detection, and persists new discoveries to the niche feed.

| | |
|---|---|
| **Auth** | QStash signature |
| **Schedule** | Hourly |

**Query params:**

| Param | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `max_age_hours` | `int` | `1` | 0-720 | Skip niches analyzed more recently than this |

**Response** `200 OK` -- same shape as scrape-creators

---

### POST /workers/publish-scheduled

Publish scheduled posts that are due. Runs on a 5-minute cron with a 120-second timeout. Picks up posts with status `scheduled` whose `scheduled_for` is in the past, downloads the file, publishes via the platform API, and updates the post status.

| | |
|---|---|
| **Auth** | QStash signature |
| **Schedule** | Every 5 minutes |

**Query params:**

| Param | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `max_posts` | `int` | `1` | 1-10 | Max posts to publish in this run |

**Response** `200 OK`

```json
{
  "published": 1,
  "failed": 0,
  "skipped": 0
}
```
