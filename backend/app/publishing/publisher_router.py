"""PublisherRouter — registry that dispatches publish calls to per-platform impls.

Mirror of `app.platforms.router.DataProviderRouter` but for the *write* side
of the platform abstraction. The publish-scheduled worker calls
`router.get(post.platform).publish(...)` and gets back a normalized
`PublishResult`.
"""

from __future__ import annotations

import logging

from app.platforms.base import Platform
from app.publishing.publishers.base import Publisher

logger = logging.getLogger(__name__)


class PublisherRouter:
    """Registry of platform publishers.

    Usage:
        router = PublisherRouter()
        router.register(YouTubeShortsPublisher(oauth_provider=yt_oauth))
        router.register(MockPublisher(Platform.LINKEDIN))

        result = await router.get(Platform.YOUTUBE).publish(
            db=db, connection=conn, post=post,
            video_bytes=bytes_, video_url=url,
        )
    """

    def __init__(self) -> None:
        self._publishers: dict[Platform, Publisher] = {}

    def register(self, publisher: Publisher) -> None:
        """Add a publisher for its platform. Replaces any existing entry."""
        existing = self._publishers.get(publisher.platform)
        if existing:
            logger.info(
                f"Replacing {existing.name} with {publisher.name} "
                f"for {publisher.platform.value}"
            )
        self._publishers[publisher.platform] = publisher

    def get(self, platform: Platform) -> Publisher | None:
        return self._publishers.get(platform)

    @property
    def registered_platforms(self) -> list[Platform]:
        return list(self._publishers.keys())

    @property
    def publisher_summary(self) -> dict[str, str]:
        """For health checks / startup logs — which publisher serves each platform."""
        return {p.value: pub.name for p, pub in self._publishers.items()}

    async def close(self) -> None:
        """Close all underlying HTTP clients (called on app shutdown)."""
        for publisher in self._publishers.values():
            try:
                await publisher.close()
            except Exception as e:
                logger.warning(f"Error closing {publisher.name}: {e}")
