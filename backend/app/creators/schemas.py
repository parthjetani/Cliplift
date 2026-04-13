"""Pydantic schemas for the creators domain."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.platforms.base import Platform


class CreatorResponse(BaseModel):
    """Public shape of a Creator row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: Platform
    platform_id: str
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    is_active: bool
    last_scraped_at: datetime | None = None
    created_at: datetime


class TrackedCreatorResponse(BaseModel):
    """Creator + tracking metadata (returned by GET /api/v1/creators)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    creator: CreatorResponse
    tracked_at: datetime
    notes: str | None = None
    # Convenience: latest snapshot's followers count
    latest_followers: int | None = None


class TrackCreatorRequest(BaseModel):
    """Body for POST /api/v1/creators/track.

    Either provide (platform + platform_id) directly, or just `url` and we'll
    parse it. URL parsing is best-effort — production should always send the
    explicit form.
    """

    platform: Platform | None = None
    platform_id: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=1000)

    def resolve(self) -> tuple[Platform, str]:
        """Return (platform, platform_id) — explicit fields take precedence over URL."""
        if self.platform and self.platform_id:
            return self.platform, self.platform_id
        if self.url:
            # Best-effort URL parsing — patterns are loose, OK for MVP
            url = self.url.strip().lower()
            if "youtube.com/" in url or "youtu.be/" in url:
                return Platform.YOUTUBE, _extract_youtube_id(url)
            if "tiktok.com/@" in url:
                return Platform.TIKTOK, _extract_tiktok_id(url)
            if "instagram.com/" in url:
                return Platform.INSTAGRAM, _extract_instagram_id(url)
            if "linkedin.com/in/" in url:
                return Platform.LINKEDIN, _extract_linkedin_id(url)
        raise ValueError(
            "Must provide either (platform + platform_id) or a recognizable creator URL"
        )


def _extract_youtube_id(url: str) -> str:
    # https://youtube.com/@username or /channel/UCxxx
    if "/@" in url:
        return "@" + url.split("/@")[1].split("/")[0].split("?")[0]
    if "/channel/" in url:
        return url.split("/channel/")[1].split("/")[0].split("?")[0]
    return url.rsplit("/", 1)[-1].split("?")[0]


def _extract_tiktok_id(url: str) -> str:
    return "@" + url.split("/@")[1].split("/")[0].split("?")[0]


def _extract_instagram_id(url: str) -> str:
    parts = url.split("instagram.com/")[1].split("/")
    return parts[0].split("?")[0]


def _extract_linkedin_id(url: str) -> str:
    return url.split("/in/")[1].split("/")[0].split("?")[0]


class CreatorSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    creator_id: uuid.UUID
    followers: int | None = None
    total_videos: int | None = None
    avg_views_30d: float | None = None
    avg_engagement_30d: float | None = None
    snapshot_date: date


class CreatorDetailResponse(BaseModel):
    """GET /api/v1/creators/{id} — creator + recent snapshots."""

    creator: CreatorResponse
    tracking: TrackedCreatorResponse | None = None
    recent_snapshots: list[CreatorSnapshotResponse]
