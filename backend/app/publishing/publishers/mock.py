"""Deterministic mock publisher.

Returns fake-but-stable `platform_post_id` values seeded by the post's UUID
so tests can assert exact return values. No external calls. Used in dev and
tests, and as the fallback for platforms whose real publisher hasn't shipped
yet (linkedin, tiktok).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.platforms.base import Platform
from app.publishing.publishers.base import Publisher, PublishResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.publishing.models import PlatformConnection, ScheduledPost


class MockPublisher(Publisher):
    """No-op publisher that returns deterministic fake post IDs."""

    name = "mock"

    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    async def publish(
        self,
        *,
        db: "AsyncSession",
        connection: "PlatformConnection",
        post: "ScheduledPost",
        video_bytes: bytes,
        video_url: str,
    ) -> PublishResult:
        platform_post_id = f"mock_{post.id.hex[:8]}"
        return PublishResult(
            platform_post_id=platform_post_id,
            published_url=(
                f"https://mock.local/{self.platform.value}/{platform_post_id}"
            ),
            published_at=datetime.now(timezone.utc),
        )
