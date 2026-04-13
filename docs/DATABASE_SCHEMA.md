# Database Schema

> 13 application tables on PostgreSQL (Supabase). Async SQLAlchemy 2.0, 2 Alembic migrations.

## Connection

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres
```

Local dev uses `npx supabase start` which runs Postgres on port 54322. The `auth.users` table is managed by Supabase — our `profiles` table FKs into it.

## Tables

### Auth domain

#### `profiles`

Extends Supabase `auth.users`. 1:1 relationship. Auto-created by a DB trigger on user signup.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | Matches `auth.users.id` (FK added via raw SQL in migration) |
| `email` | `VARCHAR(255)` | UNIQUE, NOT NULL | |
| `name` | `VARCHAR(255)` | nullable | |
| `avatar_url` | `VARCHAR(512)` | nullable | |
| `stripe_customer_id` | `VARCHAR(255)` | UNIQUE, nullable | Legacy — billing moved to Team in Week 5 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update | |

#### `teams`

Workspace scoping. Every user gets exactly one auto-created "Personal" team on first API call.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK, default `gen_random_uuid()` | |
| `name` | `VARCHAR(255)` | NOT NULL | Default: "Personal" |
| `owner_id` | `UUID` | FK → `profiles.id` ON DELETE CASCADE | |
| `plan` | `VARCHAR(32)` | NOT NULL, default `"creator"` | Values: `creator`, `team`, `agency`, `cancelled` |
| `stripe_customer_id` | `VARCHAR(255)` | UNIQUE, nullable | Set by checkout webhook |
| `stripe_subscription_id` | `VARCHAR(255)` | UNIQUE, nullable | Set by checkout webhook |
| `trial_ends_at` | `TIMESTAMPTZ` | nullable | Default `now() + 7 days` for new teams |
| `max_tracked_creators` | `INTEGER` | NOT NULL, default 3 | **Legacy** — enforcement reads `PLAN_LIMITS` dict, not this column |
| `max_seats` | `INTEGER` | NOT NULL, default 1 | **Legacy** — same |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

#### `team_members`

Membership linking Profile → Team with role.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `team_id` | `UUID` | FK → `teams.id` ON DELETE CASCADE | |
| `user_id` | `UUID` | FK → `profiles.id` ON DELETE CASCADE | |
| `role` | `VARCHAR(32)` | NOT NULL, default `"member"` | `owner` or `member` |
| `invited_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `joined_at` | `TIMESTAMPTZ` | nullable | NULL until invite accepted |

### Creator tracking domain

#### `creators`

Platform-agnostic creator records. Created on first track or discovered via search.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `platform` | `VARCHAR(32)` | NOT NULL | `youtube`, `instagram`, `linkedin`, `tiktok` |
| `platform_id` | `VARCHAR(255)` | NOT NULL | Platform-native creator ID |
| `username` | `VARCHAR(255)` | nullable | |
| `display_name` | `VARCHAR(255)` | nullable | |
| `avatar_url` | `VARCHAR(512)` | nullable | |
| `bio` | `TEXT` | nullable | |
| `is_active` | `BOOLEAN` | NOT NULL, default `true` | |
| `last_scraped_at` | `TIMESTAMPTZ` | nullable | Set by scrape-creators worker |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

**Index:** `idx_creators_platform` on `(platform, platform_id)` — unique lookup.

#### `creator_trackings`

Many-to-many: which teams track which creators.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `team_id` | `UUID` | FK → `teams.id` ON DELETE CASCADE | |
| `creator_id` | `UUID` | FK → `creators.id` ON DELETE CASCADE | |
| `tracked_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | When the team started tracking |
| `notes` | `TEXT` | nullable | User-provided notes |

**Index:** UNIQUE on `(team_id, creator_id)`.

#### `creator_snapshots`

Daily metrics snapshots populated by the `scrape-creators` worker.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `creator_id` | `UUID` | FK → `creators.id` ON DELETE CASCADE | |
| `followers` | `BIGINT` | nullable | |
| `total_videos` | `INTEGER` | nullable | |
| `avg_views_30d` | `FLOAT` | nullable | |
| `avg_engagement_30d` | `FLOAT` | nullable | |
| `snapshot_date` | `DATE` | NOT NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

**Index:** `idx_creator_snapshots_creator_date` on `(creator_id, snapshot_date)`.

### Video tracking domain

#### `videos`

Platform-agnostic video records with denormalized latest metrics.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `creator_id` | `UUID` | FK → `creators.id`, nullable | NULL for search-only videos |
| `platform` | `VARCHAR(32)` | NOT NULL | |
| `platform_video_id` | `VARCHAR(255)` | NOT NULL | |
| `title` | `VARCHAR(512)` | nullable | |
| `description` | `TEXT` | nullable | |
| `thumbnail_url` | `VARCHAR(1024)` | nullable | |
| `duration_seconds` | `INTEGER` | nullable | |
| `published_at` | `TIMESTAMPTZ` | nullable | |
| `hashtags` | `VARCHAR[]` | nullable | PostgreSQL array |
| `is_short` | `BOOLEAN` | NOT NULL, default `true` | |
| `outlier_score` | `FLOAT` | nullable | Creator-relative Z-score |
| `is_outlier` | `BOOLEAN` | NOT NULL, default `false` | `true` when `outlier_score >= 3.0` |
| `latest_views` | `BIGINT` | default 0 | Denormalized from latest snapshot |
| `latest_likes` | `BIGINT` | default 0 | |
| `latest_comments` | `BIGINT` | default 0 | |
| `latest_shares` | `BIGINT` | default 0 | |
| `latest_engagement_rate` | `FLOAT` | nullable | |
| `latest_snapshot_at` | `TIMESTAMPTZ` | nullable | |
| `last_scraped_at` | `TIMESTAMPTZ` | nullable | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

**Indexes:** `idx_videos_outlier` on `(is_outlier, outlier_score)`.

#### `video_snapshots`

6-hourly metrics snapshots with computed view velocity.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `video_id` | `UUID` | FK → `videos.id` ON DELETE CASCADE | |
| `views` | `BIGINT` | nullable | |
| `likes` | `BIGINT` | nullable | |
| `comments` | `BIGINT` | nullable | |
| `shares` | `BIGINT` | nullable | |
| `engagement_rate` | `FLOAT` | nullable | |
| `view_velocity` | `FLOAT` | nullable | `(current_views - prev_views) / hours_elapsed` |
| `snapshot_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

**Index:** `idx_video_snapshots_video_date` on `(video_id, snapshot_at)`.

#### `video_trackings`

Many-to-many: which teams track which videos.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `team_id` | `UUID` | FK → `teams.id` ON DELETE CASCADE | |
| `video_id` | `UUID` | FK → `videos.id` ON DELETE CASCADE | |
| `tracked_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

### Discovery domain

#### `niches`

User-defined keyword groups for auto-discovery.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `team_id` | `UUID` | FK → `teams.id` ON DELETE CASCADE | |
| `name` | `VARCHAR(255)` | NOT NULL | |
| `keywords` | `VARCHAR[]` | NOT NULL | 1–20 keywords |
| `platforms` | `VARCHAR[]` | NOT NULL | Which platforms to search |
| `is_active` | `BOOLEAN` | NOT NULL, default `true` | Worker skips inactive niches |
| `last_analyzed_at` | `TIMESTAMPTZ` | nullable | Set by discover-trends worker |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

#### `niche_videos`

Join table: videos discovered by a niche's keywords, with niche-relative outlier scores.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `niche_id` | `UUID` | FK → `niches.id` ON DELETE CASCADE | |
| `video_id` | `UUID` | FK → `videos.id` ON DELETE CASCADE | |
| `outlier_score` | `FLOAT` | nullable | Z-score within this niche (not creator-relative) |
| `discovered_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

**Index:** `idx_niche_videos_niche_score` on `(niche_id, outlier_score DESC)`.

### Publishing domain

#### `platform_connections`

OAuth connections to publishing platforms. Tokens are AES-256 encrypted at rest.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `team_id` | `UUID` | FK → `teams.id` ON DELETE CASCADE | |
| `platform` | `VARCHAR(32)` | NOT NULL | |
| `platform_user_id` | `VARCHAR(255)` | nullable | e.g., YouTube channel ID, IG user ID |
| `platform_username` | `VARCHAR(255)` | nullable | |
| `access_token` | `TEXT` | nullable | **Encrypted** (Fernet) |
| `refresh_token` | `TEXT` | nullable | **Encrypted** (Fernet) |
| `token_expires_at` | `TIMESTAMPTZ` | nullable | |
| `scopes` | `VARCHAR[]` | nullable | Granted OAuth scopes |
| `connected_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |

#### `scheduled_posts`

Posts scheduled for publishing. Status lifecycle: `draft → scheduled → publishing → published | failed`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `team_id` | `UUID` | FK → `teams.id` ON DELETE CASCADE | |
| `connection_id` | `UUID` | FK → `platform_connections.id` ON DELETE CASCADE | |
| `created_by` | `UUID` | FK → `profiles.id` ON DELETE SET NULL | Audit trail |
| `inspired_by_video_id` | `UUID` | FK → `videos.id` ON DELETE SET NULL | Insight → action link |
| `platform` | `VARCHAR(32)` | NOT NULL | |
| `title` | `VARCHAR(512)` | nullable | |
| `description` | `TEXT` | nullable | |
| `hashtags` | `VARCHAR[]` | nullable | |
| `file_key` | `VARCHAR(512)` | nullable | Supabase Storage object key |
| `media_url` | `VARCHAR(1024)` | nullable | Public URL (set after publish) |
| `scheduled_for` | `TIMESTAMPTZ` | NOT NULL | |
| `status` | `VARCHAR(32)` | NOT NULL, default `"draft"` | |
| `platform_post_id` | `VARCHAR(255)` | nullable | Set after successful publish |
| `error_message` | `TEXT` | nullable | Set on failure |
| `published_at` | `TIMESTAMPTZ` | nullable | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()`, on update | |

**Index:** `idx_scheduled_posts_team_status` on `(team_id, status, scheduled_for)`.

#### `post_analytics`

Snapshots of a published post's performance metrics (populated by a future worker).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `post_id` | `UUID` | FK → `scheduled_posts.id` ON DELETE CASCADE | |
| `views` | `BIGINT` | nullable | |
| `likes` | `BIGINT` | nullable | |
| `comments` | `BIGINT` | nullable | |
| `shares` | `BIGINT` | nullable | |
| `watch_time_seconds` | `BIGINT` | nullable | |
| `avg_view_duration` | `FLOAT` | nullable | |
| `snapshot_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | |
| `raw_data` | `JSONB` | nullable | Full platform response |

## Relationships diagram

```
auth.users (Supabase)
  └─1:1─> profiles
            ├─1:N─> teams (owner_id)
            │         ├─1:N─> team_members
            │         ├─1:N─> creator_trackings ──M:1──> creators
            │         │                                    └─1:N─> creator_snapshots
            │         ├─1:N─> video_trackings ──M:1──> videos
            │         │                                  └─1:N─> video_snapshots
            │         ├─1:N─> niches
            │         │         └─1:N─> niche_videos ──M:1──> videos
            │         ├─1:N─> platform_connections
            │         │         └─1:N─> scheduled_posts
            │         │                   └─1:N─> post_analytics
            │         └─ (billing: stripe_customer_id, plan, trial_ends_at)
            └─1:N─> team_members
```

## Migrations

| File | Revision | Description |
|---|---|---|
| `0001_initial.py` | `0001` | All 13 tables, indexes, FK from profiles → auth.users, auto-profile trigger |
| `0002_team_stripe_customer_id_and_trial.py` | `0002` | Adds `teams.stripe_customer_id` + `teams.trial_ends_at`, backfills trial |

Run migrations: `make migrate` (or `cd backend && alembic upgrade head`).
Create new: `make migrate-create MSG="description"`.
Reset: `make db-reset` (drops all tables + re-applies).

## SQLAlchemy mixins

Defined in `app/common/base.py`:

| Mixin | Columns added |
|---|---|
| `UUIDMixin` | `id: UUID` (PK, default `gen_random_uuid()`) |
| `TimestampMixin` | `created_at: TIMESTAMPTZ`, `updated_at: TIMESTAMPTZ` (auto-set) |
| `CreatedAtMixin` | `created_at: TIMESTAMPTZ` only (for append-only tables) |
