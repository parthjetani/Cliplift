"""Unit tests for DataProviderRouter."""

import pytest

from app.platforms.base import Platform
from app.platforms.mock import MockDataProvider
from app.platforms.router import DataProviderRouter


@pytest.fixture
def router() -> DataProviderRouter:
    r = DataProviderRouter()
    r.register(MockDataProvider(Platform.YOUTUBE))
    r.register(MockDataProvider(Platform.INSTAGRAM))
    r.register(MockDataProvider(Platform.LINKEDIN))
    r.register(MockDataProvider(Platform.TIKTOK))
    return r


class TestRouter:
    def test_register_and_get(self) -> None:
        r = DataProviderRouter()
        provider = MockDataProvider(Platform.YOUTUBE)
        r.register(provider)
        assert r.get(Platform.YOUTUBE) is provider

    def test_get_unknown_platform_returns_none(self) -> None:
        r = DataProviderRouter()
        assert r.get(Platform.YOUTUBE) is None

    def test_register_replaces_existing(self) -> None:
        r = DataProviderRouter()
        first = MockDataProvider(Platform.YOUTUBE)
        second = MockDataProvider(Platform.YOUTUBE)
        r.register(first)
        r.register(second)
        assert r.get(Platform.YOUTUBE) is second

    def test_provider_summary(self, router: DataProviderRouter) -> None:
        summary = router.provider_summary
        assert summary["youtube"] == "mock"
        assert summary["linkedin"] == "mock"
        assert len(summary) == 4

    async def test_search_single_platform(self, router: DataProviderRouter) -> None:
        results = await router.search_videos(
            query="fitness",
            platforms=[Platform.YOUTUBE],
            limit_per_platform=5,
        )
        assert Platform.YOUTUBE in results
        assert len(results[Platform.YOUTUBE]) == 5

    async def test_search_multi_platform_parallel(self, router: DataProviderRouter) -> None:
        results = await router.search_videos(
            query="fitness",
            platforms=[Platform.YOUTUBE, Platform.LINKEDIN, Platform.TIKTOK],
            limit_per_platform=5,
        )
        assert len(results) == 3
        assert all(len(v) == 5 for v in results.values())

    async def test_search_skips_unregistered_platforms(self) -> None:
        r = DataProviderRouter()
        r.register(MockDataProvider(Platform.YOUTUBE))
        results = await r.search_videos(
            query="fitness",
            platforms=[Platform.YOUTUBE, Platform.LINKEDIN],
            limit_per_platform=5,
        )
        assert Platform.YOUTUBE in results
        assert Platform.LINKEDIN not in results

    async def test_search_empty_platforms_returns_empty(
        self, router: DataProviderRouter
    ) -> None:
        results = await router.search_videos("fitness", platforms=[], limit_per_platform=5)
        assert results == {}

    async def test_get_creator_via_router(self, router: DataProviderRouter) -> None:
        creator = await router.get_creator(Platform.YOUTUBE, "channel_xyz")
        assert creator is not None
        assert creator.platform == Platform.YOUTUBE

    async def test_get_video_metrics_via_router(self, router: DataProviderRouter) -> None:
        metrics = await router.get_video_metrics(Platform.TIKTOK, "video_abc")
        assert metrics is not None
        assert metrics.platform_video_id == "video_abc"
