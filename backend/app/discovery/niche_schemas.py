"""Pydantic schemas for niche management.

Niches are user-defined keyword groups that the discover-trends worker
auto-searches across the configured platforms. The worker writes results into
the `niche_videos` join table with niche-relative outlier scores.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.platforms.base import Platform
from app.videos.schemas import VideoResponse


class NicheCreate(BaseModel):
    """Body for POST /api/v1/niches."""

    name: str = Field(..., min_length=1, max_length=255)
    keywords: list[str] = Field(
        ..., min_length=1, max_length=20, description="Search terms (1-20)"
    )
    platforms: list[Platform] = Field(
        default_factory=lambda: [
            Platform.YOUTUBE,
            Platform.INSTAGRAM,
            Platform.LINKEDIN,
            Platform.TIKTOK,
        ],
        min_length=1,
        max_length=4,
    )
    is_active: bool = True


class NicheUpdate(BaseModel):
    """Body for PUT /api/v1/niches/{id} — all fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    keywords: list[str] | None = Field(default=None, min_length=1, max_length=20)
    platforms: list[Platform] | None = Field(default=None, min_length=1, max_length=4)
    is_active: bool | None = None


class NicheResponse(BaseModel):
    """Public shape of a Niche row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    keywords: list[str]
    platforms: list[Platform]
    is_active: bool
    last_analyzed_at: datetime | None = None
    created_at: datetime


class NicheFeedItem(BaseModel):
    """A single video in a niche's auto-discovery feed.

    Wraps `VideoResponse` with the niche-relative outlier score from the
    `niche_videos` join table (separate from the creator-relative score on
    `videos.outlier_score`).
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID  # niche_videos.id
    niche_id: uuid.UUID
    discovered_at: datetime
    # Aliased: model column is `outlier_score`, but the API field is renamed
    # to disambiguate from the creator-relative score on `videos.outlier_score`
    niche_outlier_score: float | None = Field(default=None, alias="outlier_score")
    video: VideoResponse
