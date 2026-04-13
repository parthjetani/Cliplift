"""Unit tests for MockDataProvider — verifies determinism and shape."""

import pytest

from app.platforms.base import Platform, VideoSearchResult
from app.platforms.mock import MockDataProvider


@pytest.fixture
def youtube_mock() -> MockDataProvider:
    return MockDataProvider(Platform.YOUTUBE)


@pytest.fixture
def linkedin_mock() -> MockDataProvider:
    return MockDataProvider(Platform.LINKEDIN)


class TestMockSearch:
    async def test_returns_requested_count(self, youtube_mock: MockDataProvider) -> None:
        videos = await youtube_mock.search_videos("fitness", limit=15)
        assert len(videos) == 15

    async def test_results_are_video_search_results(self, youtube_mock: MockDataProvider) -> None:
        videos = await youtube_mock.search_videos("fitness", limit=5)
        assert all(isinstance(v, VideoSearchResult) for v in videos)

    async def test_platform_field_correct(self, youtube_mock: MockDataProvider) -> None:
        videos = await youtube_mock.search_videos("fitness", limit=5)
        assert all(v.platform == Platform.YOUTUBE for v in videos)

    async def test_deterministic(self, youtube_mock: MockDataProvider) -> None:
        """Same query → exactly same results."""
        a = await youtube_mock.search_videos("fitness", limit=10)
        b = await youtube_mock.search_videos("fitness", limit=10)
        assert [v.platform_video_id for v in a] == [v.platform_video_id for v in b]
        assert [v.views for v in a] == [v.views for v in b]
        assert [v.title for v in a] == [v.title for v in b]

    async def test_different_queries_different_results(
        self, youtube_mock: MockDataProvider
    ) -> None:
        a = await youtube_mock.search_videos("fitness", limit=10)
        b = await youtube_mock.search_videos("cooking", limit=10)
        assert [v.platform_video_id for v in a] != [v.platform_video_id for v in b]

    async def test_different_platforms_different_data(
        self,
        youtube_mock: MockDataProvider,
        linkedin_mock: MockDataProvider,
    ) -> None:
        a = await youtube_mock.search_videos("fitness", limit=10)
        b = await linkedin_mock.search_videos("fitness", limit=10)
        assert [v.platform_video_id for v in a] != [v.platform_video_id for v in b]
        assert all(v.platform == Platform.YOUTUBE for v in a)
        assert all(v.platform == Platform.LINKEDIN for v in b)

    async def test_metrics_are_non_negative(self, youtube_mock: MockDataProvider) -> None:
        videos = await youtube_mock.search_videos("fitness", limit=20)
        for v in videos:
            assert v.views >= 0
            assert v.likes >= 0
            assert v.comments >= 0
            assert v.shares >= 0

    async def test_includes_obvious_outliers(self, youtube_mock: MockDataProvider) -> None:
        """Mock data should have at least one video with view count >> median."""
        videos = await youtube_mock.search_videos("fitness", limit=20)
        sorted_views = sorted(v.views for v in videos)
        median = sorted_views[len(sorted_views) // 2]
        max_views = max(sorted_views)
        # Top video should be at least 5x the median (mock injects 12-25x outliers)
        assert max_views >= median * 5

    async def test_url_present(self, youtube_mock: MockDataProvider) -> None:
        videos = await youtube_mock.search_videos("fitness", limit=5)
        assert all(v.url.startswith("https://") for v in videos)


class TestMockGetCreator:
    async def test_returns_creator_profile(self, youtube_mock: MockDataProvider) -> None:
        creator = await youtube_mock.get_creator("creator_123")
        assert creator is not None
        assert creator.platform == Platform.YOUTUBE
        assert creator.platform_id == "creator_123"

    async def test_deterministic(self, youtube_mock: MockDataProvider) -> None:
        a = await youtube_mock.get_creator("creator_123")
        b = await youtube_mock.get_creator("creator_123")
        assert a.username == b.username
        assert a.followers == b.followers


class TestMockGetVideoMetrics:
    async def test_returns_metrics(self, youtube_mock: MockDataProvider) -> None:
        metrics = await youtube_mock.get_video_metrics("video_abc")
        assert metrics is not None
        assert metrics.platform_video_id == "video_abc"
        assert metrics.views >= 0

    async def test_deterministic(self, youtube_mock: MockDataProvider) -> None:
        a = await youtube_mock.get_video_metrics("video_abc")
        b = await youtube_mock.get_video_metrics("video_abc")
        assert a.views == b.views
        assert a.likes == b.likes
