"""Abstract DataProvider interface and shared schemas.

Every platform adapter (YouTube, Netrows, Data365, Mock) implements this
interface so the rest of the codebase can stay platform-agnostic.

When you swap one provider for another (e.g., Data365 → in-house TikTok scraper),
nothing outside `app/platforms/` needs to change.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Platform(str, Enum):
    """Supported short-form video platforms."""

    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"


# ----------------------------------------------------------------------------
# Shared schemas
# ----------------------------------------------------------------------------


class VideoSearchResult(BaseModel):
    """Normalized video shape returned by all providers.

    Maps cleanly to the `videos` table — when we persist a search result, the
    fields line up 1:1.
    """

    model_config = ConfigDict(extra="forbid")

    platform: Platform
    platform_video_id: str
    url: str
    title: str
    description: str | None = None

    # Creator info (denormalized into the result for convenience)
    creator_username: str
    creator_display_name: str | None = None
    creator_platform_id: str | None = None
    creator_followers: int | None = None

    # Metrics (BIGINT-safe — viral videos exceed 2.1B views)
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    engagement_rate: float | None = None

    # Metadata
    published_at: datetime | None = None
    thumbnail_url: str | None = None
    duration_seconds: int | None = None
    hashtags: list[str] = Field(default_factory=list)

    # Filled in by outlier detection (post-processing)
    outlier_score: float | None = None
    is_outlier: bool = False


class CreatorProfile(BaseModel):
    """Normalized creator shape — maps to the `creators` table."""

    model_config = ConfigDict(extra="forbid")

    platform: Platform
    platform_id: str
    username: str
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    followers: int | None = None
    following: int | None = None
    total_videos: int | None = None
    verified: bool = False


class VideoMetrics(BaseModel):
    """Snapshot of a video's current metrics — maps to `video_snapshots`."""

    model_config = ConfigDict(extra="forbid")

    platform_video_id: str
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    engagement_rate: float | None = None
    fetched_at: datetime


# ----------------------------------------------------------------------------
# Provider abstract base
# ----------------------------------------------------------------------------


class DataProvider(ABC):
    """Abstract interface every platform adapter must implement.

    Subclasses set:
        platform: Platform   # which platform this adapter serves
        name: str            # provider identifier (e.g., "youtube_official", "mock")

    Concrete adapters:
        - app.platforms.mock.MockDataProvider          (deterministic fake data)
        - app.platforms.youtube.YouTubeProvider        (YouTube Data API v3)
        - app.platforms.netrows.NetrowsProvider        (LinkedIn via Netrows)
        - app.platforms.data365.Data365Provider        (TikTok + Instagram)
    """

    platform: Platform
    name: str

    @abstractmethod
    async def search_videos(
        self,
        query: str,
        limit: int = 20,
    ) -> list[VideoSearchResult]:
        """Search for videos matching `query`. Returns at most `limit` results."""

    @abstractmethod
    async def get_creator(self, platform_id: str) -> CreatorProfile | None:
        """Fetch a creator's full profile by their platform-native ID."""

    @abstractmethod
    async def get_video_metrics(self, platform_video_id: str) -> VideoMetrics | None:
        """Fetch the latest metrics for a single video."""

    async def close(self) -> None:
        """Cleanup hook (close HTTP clients, etc.). Override if needed."""
        return None
