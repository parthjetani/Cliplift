"""Pydantic schemas for the videos domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.platforms.base import Platform


class VideoResponse(BaseModel):
    """Public shape of a Video row — denormalized latest_* fields included."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    creator_id: uuid.UUID | None = None
    platform: Platform
    platform_video_id: str
    title: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: int | None = None
    published_at: datetime | None = None
    hashtags: list[str] | None = None
    is_short: bool

    # Outlier flags (creator-relative)
    outlier_score: float | None = None
    is_outlier: bool

    # Latest denormalized metrics
    latest_views: int
    latest_likes: int
    latest_comments: int
    latest_shares: int
    latest_engagement_rate: float | None = None
    latest_snapshot_at: datetime | None = None

    created_at: datetime


class TrackedVideoResponse(BaseModel):
    """Video + tracking metadata (returned by GET /api/v1/videos)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video: VideoResponse
    tracked_at: datetime


class TrackVideoRequest(BaseModel):
    """Body for POST /api/v1/videos/track."""

    platform: Platform | None = None
    platform_video_id: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=512)

    def resolve(self) -> tuple[Platform, str]:
        if self.platform and self.platform_video_id:
            return self.platform, self.platform_video_id
        if self.url:
            url = self.url.strip().lower()
            if "youtube.com/shorts/" in url:
                return Platform.YOUTUBE, url.split("/shorts/")[1].split("?")[0].split("/")[0]
            if "youtube.com/watch?v=" in url or "youtu.be/" in url:
                if "watch?v=" in url:
                    return Platform.YOUTUBE, url.split("watch?v=")[1].split("&")[0]
                return Platform.YOUTUBE, url.split("youtu.be/")[1].split("?")[0]
            if "tiktok.com/" in url and "/video/" in url:
                return Platform.TIKTOK, url.split("/video/")[1].split("?")[0].split("/")[0]
            if "instagram.com/reel/" in url or "instagram.com/p/" in url:
                key = "/reel/" if "/reel/" in url else "/p/"
                return Platform.INSTAGRAM, url.split(key)[1].split("?")[0].split("/")[0]
            if "linkedin.com/" in url:
                return Platform.LINKEDIN, url.rsplit("/", 1)[-1].split("?")[0]
        raise ValueError(
            "Must provide (platform + platform_video_id) or a recognizable video URL"
        )


class VideoSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    engagement_rate: float | None = None
    view_velocity: float | None = None
    snapshot_at: datetime


class VideoDetailResponse(BaseModel):
    """GET /api/v1/videos/{id} — video + recent snapshots."""

    video: VideoResponse
    tracking: TrackedVideoResponse | None = None
    recent_snapshots: list[VideoSnapshotResponse]
