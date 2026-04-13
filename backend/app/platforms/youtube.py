"""YouTube Data API v3 adapter.

Free tier: 10,000 quota units/day. Costs:
- search.list:      100 units per call
- videos.list:      1 unit per call
- channels.list:    1 unit per call

Strategy: 1 search call + 1 batched videos.list call per query = 101 units.
That's ~99 searches/day on the free tier.

Falls back to MockDataProvider if YOUTUBE_API_KEY is missing.
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

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def _parse_iso8601_duration(duration: str) -> int:
    """Convert YouTube's ISO8601 duration (PT1M30S) to seconds."""
    if not duration or not duration.startswith("PT"):
        return 0
    duration = duration[2:]
    seconds = 0
    num = ""
    for ch in duration:
        if ch.isdigit():
            num += ch
        elif ch == "H":
            seconds += int(num) * 3600
            num = ""
        elif ch == "M":
            seconds += int(num) * 60
            num = ""
        elif ch == "S":
            seconds += int(num)
            num = ""
    return seconds


def _extract_hashtags(text: str | None) -> list[str]:
    """Pull #hashtags out of a description."""
    if not text:
        return []
    return [w[1:].lower() for w in text.split() if w.startswith("#") and len(w) > 1]


class YouTubeProvider(DataProvider):
    """YouTube Data API v3 adapter."""

    platform = Platform.YOUTUBE
    name = "youtube_official"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        params["key"] = self.api_key
        response = await self._client.get(f"{YOUTUBE_API_BASE}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()

    async def search_videos(
        self,
        query: str,
        limit: int = 20,
    ) -> list[VideoSearchResult]:
        try:
            # Step 1: search.list to get video IDs (100 units)
            search_data = await self._get(
                "search",
                {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "videoDuration": "short",  # < 4 minutes — closest filter to "Shorts"
                    "maxResults": min(limit, 50),
                    "order": "viewCount",
                },
            )

            video_ids = [
                item["id"]["videoId"]
                for item in search_data.get("items", [])
                if item.get("id", {}).get("videoId")
            ]
            if not video_ids:
                return []

            # Step 2: videos.list to get statistics + duration (1 unit)
            videos_data = await self._get(
                "videos",
                {
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(video_ids),
                },
            )

            results: list[VideoSearchResult] = []
            for item in videos_data.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                content = item.get("contentDetails", {})

                views = int(stats.get("viewCount", 0))
                likes = int(stats.get("likeCount", 0))
                comments = int(stats.get("commentCount", 0))
                engagement = (likes + comments) / views if views > 0 else 0.0
                duration = _parse_iso8601_duration(content.get("duration", ""))

                # Filter to actual Shorts (≤60s)
                if duration > 60:
                    continue

                published_at = None
                if snippet.get("publishedAt"):
                    published_at = datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    )

                results.append(
                    VideoSearchResult(
                        platform=Platform.YOUTUBE,
                        platform_video_id=item["id"],
                        url=f"https://youtube.com/shorts/{item['id']}",
                        title=snippet.get("title", ""),
                        description=snippet.get("description"),
                        creator_username=snippet.get("channelTitle", ""),
                        creator_display_name=snippet.get("channelTitle"),
                        creator_platform_id=snippet.get("channelId"),
                        views=views,
                        likes=likes,
                        comments=comments,
                        shares=0,  # YouTube API does not expose shares
                        engagement_rate=round(engagement, 4),
                        published_at=published_at,
                        thumbnail_url=snippet.get("thumbnails", {})
                        .get("high", {})
                        .get("url"),
                        duration_seconds=duration,
                        hashtags=_extract_hashtags(snippet.get("description")),
                    )
                )

            return results[:limit]

        except httpx.HTTPStatusError as e:
            logger.error(f"YouTube API error: {e.response.status_code} {e.response.text[:200]}")
            return []
        except httpx.HTTPError as e:
            logger.error(f"YouTube HTTP error: {e}")
            return []

    async def get_creator(self, platform_id: str) -> CreatorProfile | None:
        try:
            data = await self._get(
                "channels",
                {"part": "snippet,statistics", "id": platform_id},
            )
            items = data.get("items", [])
            if not items:
                return None
            channel = items[0]
            snippet = channel.get("snippet", {})
            stats = channel.get("statistics", {})

            return CreatorProfile(
                platform=Platform.YOUTUBE,
                platform_id=channel["id"],
                username=snippet.get("customUrl", "").lstrip("@") or channel["id"],
                display_name=snippet.get("title"),
                avatar_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                bio=snippet.get("description"),
                followers=int(stats.get("subscriberCount", 0)),
                total_videos=int(stats.get("videoCount", 0)),
            )
        except httpx.HTTPError as e:
            logger.error(f"YouTube get_creator error: {e}")
            return None

    async def get_video_metrics(self, platform_video_id: str) -> VideoMetrics | None:
        try:
            data = await self._get(
                "videos", {"part": "statistics", "id": platform_video_id}
            )
            items = data.get("items", [])
            if not items:
                return None
            stats = items[0].get("statistics", {})
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
            engagement = (likes + comments) / views if views > 0 else 0.0

            return VideoMetrics(
                platform_video_id=platform_video_id,
                views=views,
                likes=likes,
                comments=comments,
                shares=0,
                engagement_rate=round(engagement, 4),
                fetched_at=datetime.now(timezone.utc),
            )
        except httpx.HTTPError as e:
            logger.error(f"YouTube get_video_metrics error: {e}")
            return None
