"""Pydantic schemas for the discovery domain (search, trends, outliers, AI briefs)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas import ContentBrief
from app.platforms.base import Platform, VideoSearchResult


class SearchRequest(BaseModel):
    """Body for POST /api/v1/discover/search."""

    query: str = Field(..., min_length=1, max_length=200, description="Search keywords")
    platforms: list[Platform] = Field(
        default_factory=lambda: [
            Platform.YOUTUBE,
            Platform.INSTAGRAM,
            Platform.LINKEDIN,
            Platform.TIKTOK,
        ],
        min_length=1,
        max_length=4,
        description="Which platforms to search",
    )
    limit_per_platform: int = Field(
        default=20, ge=1, le=50, description="Max results per platform"
    )
    outlier_threshold: float = Field(
        default=3.0, ge=1.0, le=5.0, description="Z-score threshold for outlier flag"
    )


class PlatformResultSummary(BaseModel):
    """Per-platform stats in a search response."""

    model_config = ConfigDict(extra="forbid")

    platform: Platform
    count: int
    outlier_count: int


class SearchResponse(BaseModel):
    """Response shape for POST /api/v1/discover/search."""

    model_config = ConfigDict(extra="forbid")

    query: str
    total: int
    outlier_count: int
    by_platform: list[PlatformResultSummary]
    videos: list[VideoSearchResult]


class GenerateIdeaRequest(BaseModel):
    """Body for POST /api/v1/discover/generate-idea."""

    video_id: uuid.UUID = Field(description="ID of the video to generate a brief from")


class GenerateIdeaResponse(BaseModel):
    """Wraps the ContentBrief with the video_id for correlation."""

    video_id: uuid.UUID
    brief: ContentBrief
