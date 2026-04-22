/**
 * TypeScript types mirroring the backend Pydantic schemas.
 *
 * Each section below corresponds to a backend domain module:
 *
 *   Section              → Backend schema source
 *   ─────────────────────────────────────────────
 *   Platform / Discovery → app/platforms/base.py + app/discovery/schemas.py
 *   Auth / Profile       → app/auth/schemas.py
 *   Pagination           → app/common/pagination.py
 *   Creators             → app/creators/schemas.py
 *   Videos               → app/videos/schemas.py
 *   Niches               → app/discovery/niche_schemas.py
 *   Connections (OAuth)  → app/publishing/oauth_schemas.py
 *   Analytics            → app/analytics/schemas.py
 *   AI Content Brief     → app/ai/schemas.py + app/discovery/schemas.py
 *   Team + Billing       → app/auth/schemas.py + app/billing/schemas.py
 *   Publishing           → app/publishing/schemas.py
 *
 * Keep these in sync manually. When OpenAPI codegen lands, this file
 * becomes generated.
 */

export type Platform = "youtube" | "instagram" | "linkedin" | "tiktok";

export const PLATFORMS: Platform[] = [
  "youtube",
  "instagram",
  "linkedin",
  "tiktok",
];

export const PLATFORM_LABELS: Record<Platform, string> = {
  youtube: "YouTube Shorts",
  instagram: "Instagram Reels",
  linkedin: "LinkedIn Video",
  tiktok: "TikTok",
};

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

export interface VideoSearchResult {
  platform: Platform;
  platform_video_id: string;
  url: string;
  title: string;
  description: string | null;

  creator_username: string;
  creator_display_name: string | null;
  creator_platform_id: string | null;
  creator_followers: number | null;

  views: number;
  likes: number;
  comments: number;
  shares: number;
  engagement_rate: number | null;

  published_at: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  hashtags: string[];

  outlier_score: number | null;
  is_outlier: boolean;
}

export interface PlatformResultSummary {
  platform: Platform;
  count: number;
  outlier_count: number;
}

export interface SearchRequest {
  query: string;
  platforms?: Platform[];
  limit_per_platform?: number;
  outlier_threshold?: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  outlier_count: number;
  by_platform: PlatformResultSummary[];
  videos: VideoSearchResult[];
}

// ---------------------------------------------------------------------------
// Auth / Profile
// ---------------------------------------------------------------------------

export interface ProfileResponse {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  stripe_customer_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileUpdate {
  name?: string;
  avatar_url?: string;
}

// ---------------------------------------------------------------------------
// Pagination envelope
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

// ---------------------------------------------------------------------------
// Creators
// ---------------------------------------------------------------------------

export interface Creator {
  id: string;
  platform: Platform;
  platform_id: string;
  username: string | null;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  is_active: boolean;
  last_scraped_at: string | null;
  created_at: string;
}

export interface TrackedCreator {
  id: string;
  creator: Creator;
  tracked_at: string;
  notes: string | null;
  latest_followers: number | null;
}

export interface TrackCreatorRequest {
  platform?: Platform;
  platform_id?: string;
  url?: string;
  notes?: string;
}

export interface CreatorSnapshot {
  id: string;
  creator_id: string;
  followers: number | null;
  total_videos: number | null;
  avg_views_30d: number | null;
  avg_engagement_30d: number | null;
  snapshot_date: string;
}

export interface CreatorDetail {
  creator: Creator;
  tracking: TrackedCreator | null;
  recent_snapshots: CreatorSnapshot[];
}

// ---------------------------------------------------------------------------
// Videos
// ---------------------------------------------------------------------------

export interface Video {
  id: string;
  creator_id: string | null;
  platform: Platform;
  platform_video_id: string;
  title: string | null;
  description: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  published_at: string | null;
  hashtags: string[] | null;
  is_short: boolean;
  outlier_score: number | null;
  is_outlier: boolean;
  latest_views: number;
  latest_likes: number;
  latest_comments: number;
  latest_shares: number;
  latest_engagement_rate: number | null;
  latest_snapshot_at: string | null;
  created_at: string;
}

export interface TrackedVideo {
  id: string;
  video: Video;
  tracked_at: string;
}

export interface TrackVideoRequest {
  platform?: Platform;
  platform_video_id?: string;
  url?: string;
}

export interface VideoSnapshot {
  id: string;
  video_id: string;
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  engagement_rate: number | null;
  view_velocity: number | null;
  snapshot_at: string;
}

export interface VideoDetail {
  video: Video;
  tracking: TrackedVideo | null;
  recent_snapshots: VideoSnapshot[];
}

// ---------------------------------------------------------------------------
// Niches
// ---------------------------------------------------------------------------

export interface Niche {
  id: string;
  team_id: string;
  name: string;
  keywords: string[];
  platforms: Platform[];
  is_active: boolean;
  last_analyzed_at: string | null;
  created_at: string;
}

export interface NicheCreate {
  name: string;
  keywords: string[];
  platforms?: Platform[];
  is_active?: boolean;
}

export interface NicheUpdate {
  name?: string;
  keywords?: string[];
  platforms?: Platform[];
  is_active?: boolean;
}

export interface NicheFeedItem {
  id: string;
  niche_id: string;
  discovered_at: string;
  outlier_score: number | null;
  video: Video;
}

// ---------------------------------------------------------------------------
// Platform connections (OAuth)
// ---------------------------------------------------------------------------

export interface PlatformConnection {
  id: string;
  platform: Platform;
  platform_user_id: string | null;
  platform_username: string | null;
  scopes: string[] | null;
  token_expires_at: string | null;
  connected_at: string;
  is_expired: boolean;
}

export interface AuthorizeResponse {
  authorize_url: string;
  state: string;
  platform: Platform;
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface OverviewResponse {
  tracked_creators: number;
  tracked_videos: number;
  active_niches: number;
  total_outliers: number;
  recent_snapshots_24h: number;
}

export interface CreatorTimelinePoint {
  snapshot_date: string;
  followers: number | null;
  total_videos: number | null;
  avg_views_30d: number | null;
  avg_engagement_30d: number | null;
}

export interface CreatorTimelineResponse {
  creator_id: string;
  days: number;
  points: CreatorTimelinePoint[];
}

export interface VideoTimelinePoint {
  snapshot_at: string;
  views: number | null;
  likes: number | null;
  comments: number | null;
  engagement_rate: number | null;
  view_velocity: number | null;
}

export interface VideoTimelineResponse {
  video_id: string;
  hours: number;
  points: VideoTimelinePoint[];
}

export interface NichePlatformBreakdown {
  platform: string;
  count: number;
}

export interface NichePerformanceDay {
  day: string;
  videos_discovered: number;
  outliers: number;
}

export interface NichePerformanceResponse {
  niche_id: string;
  days: number;
  total_videos: number;
  total_outliers: number;
  platform_breakdown: NichePlatformBreakdown[];
  daily: NichePerformanceDay[];
}

export interface RecentOutlier {
  niche_video_id: string;
  niche_id: string;
  niche_name: string;
  outlier_score: number;
  discovered_at: string;
  video_id: string;
  platform: Platform;
  title: string | null;
  thumbnail_url: string | null;
  views: number;
  likes: number;
  engagement_rate: number | null;
}

export interface RecentOutliersResponse {
  items: RecentOutlier[];
  total: number;
}

// ---------------------------------------------------------------------------
// AI Content Brief
// ---------------------------------------------------------------------------

export interface ContentBrief {
  hook_analysis: string;
  format: string;
  suggested_hook: string;
  suggested_caption: string;
  suggested_hashtags: string[];
  cta: string;
  generated_at: string;
  cached: boolean;
}

export interface GenerateIdeaRequest {
  video_id: string;
}

export interface GenerateIdeaResponse {
  video_id: string;
  brief: ContentBrief;
}

// ---------------------------------------------------------------------------
// Team + Billing
// ---------------------------------------------------------------------------

export interface TeamResponse {
  id: string;
  name: string;
  owner_id: string;
  plan: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  trial_ends_at: string | null;
  created_at: string;
  is_trial_active: boolean;
  is_trial_expired: boolean;
}

export interface CheckoutSessionRequest {
  plan: "creator" | "team" | "agency";
  billing_period: "monthly" | "annual";
}

export interface CheckoutSessionResponse {
  checkout_url: string;
  session_id: string;
}

export interface BillingPortalResponse {
  portal_url: string;
}

// ---------------------------------------------------------------------------
// Publishing — presign + scheduled posts
// ---------------------------------------------------------------------------

export type PostStatus =
  | "draft"
  | "scheduled"
  | "publishing"
  | "published"
  | "failed";

export const POST_STATUS_LABELS: Record<PostStatus, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  publishing: "Publishing",
  published: "Published",
  failed: "Failed",
};

export interface PresignRequest {
  filename: string;
  content_type: string;
}

export interface PresignResponse {
  upload_url: string;
  file_key: string;
  expires_at: string;
}

export interface ScheduledPostCreate {
  connection_id: string;
  platform: Platform;
  file_key: string;
  title?: string | null;
  description?: string | null;
  hashtags?: string[] | null;
  scheduled_for: string;
  inspired_by_video_id?: string | null;
}

export interface ScheduledPostUpdate {
  title?: string | null;
  description?: string | null;
  hashtags?: string[] | null;
  scheduled_for?: string | null;
  inspired_by_video_id?: string | null;
  status?: PostStatus | null;
}

export interface ScheduledPostResponse {
  id: string;
  team_id: string;
  connection_id: string;
  created_by: string | null;
  inspired_by_video_id: string | null;

  platform: Platform;
  title: string | null;
  description: string | null;
  hashtags: string[] | null;
  file_key: string | null;
  media_url: string | null;

  scheduled_for: string;
  status: PostStatus;
  platform_post_id: string | null;
  error_message: string | null;
  published_at: string | null;

  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// API error envelope (matches backend app/common/errors.py)
// ---------------------------------------------------------------------------

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
