"""Tests for build_publisher_router — every platform must have a publisher."""

from __future__ import annotations

from app.config import Settings
from app.platforms.base import Platform
from app.publishing.publisher_router import PublisherRouter
from app.publishing.publishers.factory import build_publisher_router
from app.publishing.publishers.instagram import InstagramReelsPublisher
from app.publishing.publishers.mock import MockPublisher
from app.publishing.publishers.youtube import YouTubeShortsPublisher


class TestBuildPublisherRouter:
    def test_router_has_all_four_platforms(self) -> None:
        """Every Platform enum value must resolve to a publisher,
        regardless of which env vars happen to be set."""
        router = build_publisher_router(Settings())
        assert isinstance(router, PublisherRouter)
        for platform in Platform:
            publisher = router.get(platform)
            assert publisher is not None, f"missing publisher for {platform}"
            assert publisher.platform == platform

    def test_youtube_real_when_google_credentials_set(self) -> None:
        s = Settings(
            GOOGLE_OAUTH_CLIENT_ID="real-client-id",
            GOOGLE_OAUTH_CLIENT_SECRET="real-secret",
        )
        router = build_publisher_router(s)
        assert isinstance(router.get(Platform.YOUTUBE), YouTubeShortsPublisher)

    def test_youtube_mock_when_google_credentials_missing(self) -> None:
        """Without real Google OAuth env vars, YouTube must fall back to
        MockPublisher — calling the real YouTube API with mock OAuth tokens
        would just 401, so end-to-end mock is the only sensible local default."""
        s = Settings(
            GOOGLE_OAUTH_CLIENT_ID="",
            GOOGLE_OAUTH_CLIENT_SECRET="",
        )
        router = build_publisher_router(s)
        yt = router.get(Platform.YOUTUBE)
        assert isinstance(yt, MockPublisher)
        assert yt.platform == Platform.YOUTUBE

    def test_instagram_real_when_meta_credentials_set(self) -> None:
        s = Settings(
            META_OAUTH_CLIENT_ID="real-client-id",
            META_OAUTH_CLIENT_SECRET="real-secret",
        )
        router = build_publisher_router(s)
        assert isinstance(
            router.get(Platform.INSTAGRAM), InstagramReelsPublisher
        )

    def test_instagram_mock_when_meta_credentials_missing(self) -> None:
        s = Settings(
            META_OAUTH_CLIENT_ID="",
            META_OAUTH_CLIENT_SECRET="",
        )
        router = build_publisher_router(s)
        ig = router.get(Platform.INSTAGRAM)
        assert isinstance(ig, MockPublisher)
        assert ig.platform == Platform.INSTAGRAM

    def test_linkedin_and_tiktok_are_mocks(self) -> None:
        router = build_publisher_router(Settings())
        assert isinstance(router.get(Platform.LINKEDIN), MockPublisher)
        assert isinstance(router.get(Platform.TIKTOK), MockPublisher)

    def test_summary_includes_all_platforms(self) -> None:
        router = build_publisher_router(Settings())
        summary = router.publisher_summary
        assert set(summary.keys()) == {p.value for p in Platform}
