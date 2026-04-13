"""Netrows API adapter for LinkedIn video data.

Netrows is our differentiator — €49/mo for LinkedIn video competitive intel
that nobody else provides. The API returns LinkedIn posts with engagement
metrics (reactions, comments, reposts).

Note: Netrows endpoint paths and field names are based on their public docs as
of April 2026. If their API changes, only this file needs updating — the
DataProvider interface stays stable for the rest of the codebase.

Falls back to MockDataProvider when NETROWS_API_KEY is missing.
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

NETROWS_API_BASE = "https://api.netrows.com/v1"


class NetrowsProvider(DataProvider):
    """Netrows adapter for LinkedIn video posts."""

    platform = Platform.LINKEDIN
    name = "netrows"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=15.0,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def search_videos(
        self,
        query: str,
        limit: int = 20,
    ) -> list[VideoSearchResult]:
        try:
            response = await self._client.get(
                f"{NETROWS_API_BASE}/linkedin/posts/search",
                params={
                    "query": query,
                    "post_type": "video",
                    "limit": min(limit, 50),
                    "sort": "engagement_desc",
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Netrows search error: {e}")
            return []

        return [self._map_post(post) for post in data.get("posts", [])][:limit]

    def _map_post(self, post: dict[str, Any]) -> VideoSearchResult:
        """Convert a Netrows LinkedIn post into our normalized shape."""
        author = post.get("author", {})

        # LinkedIn reactions are split: like, celebrate, support, love, insightful, funny
        reactions = post.get("reactions", {})
        total_reactions = sum(
            reactions.get(k, 0)
            for k in ("like", "celebrate", "support", "love", "insightful", "funny")
        )

        views = int(post.get("video_views", 0) or post.get("impressions", 0))
        comments = int(post.get("comments_count", 0))
        shares = int(post.get("reposts_count", 0))
        engagement = (total_reactions + comments + shares) / views if views > 0 else 0.0

        published_at = None
        if post.get("posted_at"):
            try:
                published_at = datetime.fromisoformat(
                    post["posted_at"].replace("Z", "+00:00")
                )
            except ValueError:
                pass

        return VideoSearchResult(
            platform=Platform.LINKEDIN,
            platform_video_id=post.get("urn") or post.get("id", ""),
            url=post.get("url", ""),
            title=post.get("text", "")[:140] or "(LinkedIn video post)",
            description=post.get("text"),
            creator_username=author.get("public_id", "") or author.get("urn", ""),
            creator_display_name=author.get("name"),
            creator_platform_id=author.get("urn"),
            creator_followers=int(author.get("followers", 0) or 0),
            views=views,
            likes=total_reactions,
            comments=comments,
            shares=shares,
            engagement_rate=round(engagement, 4),
            published_at=published_at,
            thumbnail_url=post.get("video_thumbnail"),
            duration_seconds=int(post.get("video_duration_seconds", 0) or 0),
            hashtags=post.get("hashtags", []),
        )

    async def get_creator(self, platform_id: str) -> CreatorProfile | None:
        try:
            response = await self._client.get(
                f"{NETROWS_API_BASE}/linkedin/profiles/{platform_id}"
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Netrows get_creator error: {e}")
            return None

        return CreatorProfile(
            platform=Platform.LINKEDIN,
            platform_id=platform_id,
            username=data.get("public_id", platform_id),
            display_name=data.get("name"),
            avatar_url=data.get("profile_picture"),
            bio=data.get("headline"),
            followers=int(data.get("followers", 0) or 0),
            following=int(data.get("connections", 0) or 0),
            verified=data.get("verified", False),
        )

    async def get_video_metrics(self, platform_video_id: str) -> VideoMetrics | None:
        try:
            response = await self._client.get(
                f"{NETROWS_API_BASE}/linkedin/posts/{platform_video_id}"
            )
            response.raise_for_status()
            post = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Netrows get_video_metrics error: {e}")
            return None

        reactions = post.get("reactions", {})
        total_reactions = sum(
            reactions.get(k, 0)
            for k in ("like", "celebrate", "support", "love", "insightful", "funny")
        )
        views = int(post.get("video_views", 0) or post.get("impressions", 0))
        comments = int(post.get("comments_count", 0))
        shares = int(post.get("reposts_count", 0))
        engagement = (total_reactions + comments + shares) / views if views > 0 else 0.0

        return VideoMetrics(
            platform_video_id=platform_video_id,
            views=views,
            likes=total_reactions,
            comments=comments,
            shares=shares,
            engagement_rate=round(engagement, 4),
            fetched_at=datetime.now(timezone.utc),
        )
