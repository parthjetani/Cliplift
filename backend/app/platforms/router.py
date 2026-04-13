"""DataProviderRouter — registry that dispatches calls to per-platform adapters.

This is the central abstraction for the data layer. The rest of the codebase
calls `router.search_videos(query, [Platform.YOUTUBE, Platform.LINKEDIN])` and
gets back a normalized result — agnostic to whether each platform is served by
the official API, a third-party data provider, or a mock.
"""

import asyncio
import logging
from typing import Mapping

from app.platforms.base import (
    CreatorProfile,
    DataProvider,
    Platform,
    VideoMetrics,
    VideoSearchResult,
)

logger = logging.getLogger(__name__)


class DataProviderRouter:
    """Registry of platform adapters with parallel multi-platform search.

    Usage:
        router = DataProviderRouter()
        router.register(YouTubeProvider(api_key=...))
        router.register(MockDataProvider(Platform.LINKEDIN))

        results = await router.search_videos("fitness", [Platform.YOUTUBE, Platform.LINKEDIN])
        # → {Platform.YOUTUBE: [...], Platform.LINKEDIN: [...]}
    """

    def __init__(self) -> None:
        self._providers: dict[Platform, DataProvider] = {}

    def register(self, provider: DataProvider) -> None:
        """Add a provider for its platform. Replaces any existing provider for that platform."""
        existing = self._providers.get(provider.platform)
        if existing:
            logger.info(
                f"Replacing {existing.name} with {provider.name} for {provider.platform.value}"
            )
        self._providers[provider.platform] = provider

    def get(self, platform: Platform) -> DataProvider | None:
        return self._providers.get(platform)

    @property
    def registered_platforms(self) -> list[Platform]:
        return list(self._providers.keys())

    @property
    def provider_summary(self) -> dict[str, str]:
        """For health checks / startup logs — which provider serves each platform."""
        return {p.value: prov.name for p, prov in self._providers.items()}

    async def search_videos(
        self,
        query: str,
        platforms: list[Platform],
        limit_per_platform: int = 20,
    ) -> dict[Platform, list[VideoSearchResult]]:
        """Search a query across multiple platforms in parallel.

        Returns a dict mapping each requested platform → its results. Platforms
        without a registered provider are skipped (with a warning). Failed
        provider calls return an empty list rather than raising — partial
        results are better than total failure.
        """
        tasks: list[asyncio.Task] = []
        valid_platforms: list[Platform] = []

        for platform in platforms:
            provider = self._providers.get(platform)
            if provider is None:
                logger.warning(f"No provider registered for {platform.value}, skipping")
                continue
            tasks.append(asyncio.create_task(provider.search_videos(query, limit_per_platform)))
            valid_platforms.append(platform)

        if not tasks:
            return {}

        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[Platform, list[VideoSearchResult]] = {}
        for platform, outcome in zip(valid_platforms, gathered):
            if isinstance(outcome, Exception):
                logger.error(f"Provider {platform.value} raised: {outcome}")
                results[platform] = []
            else:
                results[platform] = outcome

        return results

    async def get_creator(
        self, platform: Platform, platform_id: str
    ) -> CreatorProfile | None:
        provider = self._providers.get(platform)
        if not provider:
            return None
        return await provider.get_creator(platform_id)

    async def get_video_metrics(
        self, platform: Platform, platform_video_id: str
    ) -> VideoMetrics | None:
        provider = self._providers.get(platform)
        if not provider:
            return None
        return await provider.get_video_metrics(platform_video_id)

    async def close(self) -> None:
        """Close all underlying HTTP clients (called on app shutdown)."""
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception as e:
                logger.warning(f"Error closing {provider.name}: {e}")
