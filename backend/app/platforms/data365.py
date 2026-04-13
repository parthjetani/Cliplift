"""Data365 API adapter for TikTok and Instagram.

Data365 ($99/mo) provides public competitive intelligence on TikTok + Instagram.
A single Data365 instance handles both platforms — we register two adapters
(one per platform) sharing the same API key.

Falls back to MockDataProvider when DATA365_API_KEY is missing.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.platforms.base import (
    CreatorProfile,
    DataProvider,
    Platform,
    VideoMetrics,
    VideoSearchResult,
)

logger = logging.getLogger(__name__)

DATA365_API_BASE = "https://data365.co/api/v1"


class Data365Provider(DataProvider):
    """Data365 adapter — instantiate twice (one for TikTok, one for Instagram)."""

    name = "data365"

    def __init__(self, api_key: str, platform: Platform) -> None:
        if platform not in (Platform.TIKTOK, Platform.INSTAGRAM):
            raise ValueError(f"Data365 does not support {platform}")
        self.platform = platform
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=15.0,
            params={"access_token": api_key},
        )

    async def close(self) -> None:
        await self._client.aclose()

    @property
    def _platform_path(self) -> str:
        """Data365 uses different URL prefixes per platform."""
        return "tiktok" if self.platform == Platform.TIKTOK else "instagram"

    async def search_videos(
        self,
        query: str,
        limit: int = 20,
    ) -> list[VideoSearchResult]:
        try:
            response = await self._client.get(
                f"{DATA365_API_BASE}/{self._platform_path}/search/videos",
                params={"query": query, "limit": min(limit, 50)},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Data365 ({self.platform.value}) search error: {e}")
            return []

        return [self._map_video(v) for v in data.get("data", {}).get("items", [])][:limit]

    def _map_video(self, item: dict[str, Any]) -> VideoSearchResult:
        author = item.get("author", {})
        stats = item.get("statistics", {})

        views = int(stats.get("play_count", 0) or stats.get("view_count", 0))
        likes = int(stats.get("digg_count", 0) or stats.get("like_count", 0))
        comments = int(stats.get("comment_count", 0))
        shares = int(stats.get("share_count", 0))
        engagement = (likes + comments + shares) / views if views > 0 else 0.0

        published_at = None
        if item.get("create_time"):
            try:
                # TikTok uses unix timestamp, Instagram uses ISO
                if isinstance(item["create_time"], (int, float)):
                    published_at = datetime.fromtimestamp(
                        item["create_time"], tz=timezone.utc
                    )
                else:
                    published_at = datetime.fromisoformat(
                        str(item["create_time"]).replace("Z", "+00:00")
                    )
            except (ValueError, TypeError):
                pass

        # Build the canonical URL based on platform
        platform_video_id = str(item.get("id", ""))
        if self.platform == Platform.TIKTOK:
            url = f"https://www.tiktok.com/@{author.get('unique_id', '')}/video/{platform_video_id}"
        else:
            url = f"https://www.instagram.com/reel/{item.get('shortcode', platform_video_id)}/"

        hashtags = []
        for tag in item.get("hashtags", []) or []:
            if isinstance(tag, dict):
                hashtags.append(tag.get("name", ""))
            else:
                hashtags.append(str(tag).lstrip("#"))

        return VideoSearchResult(
            platform=self.platform,
            platform_video_id=platform_video_id,
            url=url,
            title=item.get("title") or item.get("description", "")[:140] or "(no title)",
            description=item.get("description"),
            creator_username=author.get("unique_id") or author.get("username", ""),
            creator_display_name=author.get("nickname") or author.get("full_name"),
            creator_platform_id=str(author.get("id", "")),
            creator_followers=int(author.get("follower_count", 0) or 0),
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            engagement_rate=round(engagement, 4),
            published_at=published_at,
            thumbnail_url=item.get("cover") or item.get("thumbnail_url"),
            duration_seconds=int(item.get("duration", 0) or 0),
            hashtags=[h for h in hashtags if h],
        )

    async def get_creator(self, platform_id: str) -> CreatorProfile | None:
        try:
            response = await self._client.get(
                f"{DATA365_API_BASE}/{self._platform_path}/users/{platform_id}"
            )
            response.raise_for_status()
            data = response.json().get("data", {})
        except httpx.HTTPError as e:
            logger.error(f"Data365 get_creator error: {e}")
            return None

        return CreatorProfile(
            platform=self.platform,
            platform_id=platform_id,
            username=data.get("unique_id") or data.get("username", ""),
            display_name=data.get("nickname") or data.get("full_name"),
            avatar_url=data.get("avatar") or data.get("profile_pic_url"),
            bio=data.get("signature") or data.get("biography"),
            followers=int(data.get("follower_count", 0) or 0),
            following=int(data.get("following_count", 0) or 0),
            total_videos=int(data.get("video_count", 0) or 0),
            verified=bool(data.get("verified", False)),
        )

    async def get_video_metrics(self, platform_video_id: str) -> VideoMetrics | None:
        try:
            response = await self._client.get(
                f"{DATA365_API_BASE}/{self._platform_path}/videos/{platform_video_id}"
            )
            response.raise_for_status()
            item = response.json().get("data", {})
        except httpx.HTTPError as e:
            logger.error(f"Data365 get_video_metrics error: {e}")
            return None

        stats = item.get("statistics", {})
        views = int(stats.get("play_count", 0) or stats.get("view_count", 0))
        likes = int(stats.get("digg_count", 0) or stats.get("like_count", 0))
        comments = int(stats.get("comment_count", 0))
        shares = int(stats.get("share_count", 0))
        engagement = (likes + comments + shares) / views if views > 0 else 0.0

        return VideoMetrics(
            platform_video_id=platform_video_id,
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            engagement_rate=round(engagement, 4),
            fetched_at=datetime.now(timezone.utc),
        )
