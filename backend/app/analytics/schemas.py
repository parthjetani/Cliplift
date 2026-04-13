"""Pydantic schemas for the analytics domain."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.platforms.base import Platform


class OverviewResponse(BaseModel):
    """Top-level dashboard stats for a team."""

    tracked_creators: int = 0
    tracked_videos: int = 0
    active_niches: int = 0
    total_outliers: int = 0
    recent_snapshots_24h: int = 0


class CreatorTimelinePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_date: date
    followers: int | None = None
    total_videos: int | None = None
    avg_views_30d: float | None = None
    avg_engagement_30d: float | None = None


class CreatorTimelineResponse(BaseModel):
    creator_id: uuid.UUID
    days: int
    points: list[CreatorTimelinePoint]


class VideoTimelinePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_at: datetime
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    engagement_rate: float | None = None
    view_velocity: float | None = None


class VideoTimelineResponse(BaseModel):
    video_id: uuid.UUID
    hours: int
    points: list[VideoTimelinePoint]


class NichePlatformBreakdown(BaseModel):
    platform: str
    count: int


class NichePerformanceDay(BaseModel):
    day: date
    videos_discovered: int
    outliers: int


class NichePerformanceResponse(BaseModel):
    niche_id: uuid.UUID
    days: int
    total_videos: int
    total_outliers: int
    platform_breakdown: list[NichePlatformBreakdown]
    daily: list[NichePerformanceDay]


class RecentOutlier(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    niche_video_id: uuid.UUID
    niche_id: uuid.UUID
    niche_name: str
    outlier_score: float
    discovered_at: datetime

    # Video fields (denormalized for convenience)
    video_id: uuid.UUID
    platform: Platform
    title: str | None = None
    thumbnail_url: str | None = None
    views: int = 0
    likes: int = 0
    engagement_rate: float | None = None


class RecentOutliersResponse(BaseModel):
    items: list[RecentOutlier]
    total: int
