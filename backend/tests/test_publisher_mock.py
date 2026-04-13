"""Tests for MockPublisher — deterministic, no external calls."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platforms.base import Platform
from app.publishing.publishers.base import PublishResult
from app.publishing.publishers.mock import MockPublisher


def _fake_post(post_id: uuid.UUID | None = None) -> MagicMock:
    """Lightweight stand-in for a ScheduledPost row."""
    post = MagicMock()
    post.id = post_id or uuid.uuid4()
    post.title = "Test post"
    post.description = "A test post"
    post.hashtags = ["test"]
    return post


def _fake_connection() -> MagicMock:
    conn = MagicMock()
    conn.id = uuid.uuid4()
    conn.access_token = "encrypted-fake"
    return conn


class TestMockPublisher:
    async def test_returns_valid_publish_result(self) -> None:
        publisher = MockPublisher(Platform.YOUTUBE)
        result = await publisher.publish(
            db=AsyncMock(),
            connection=_fake_connection(),
            post=_fake_post(),
            video_bytes=b"fake video",
            video_url="https://example.com/v.mp4",
        )
        assert isinstance(result, PublishResult)
        assert result.platform_post_id.startswith("mock_")
        assert "youtube" in result.published_url
        assert isinstance(result.published_at, datetime)

    async def test_deterministic_for_same_post_id(self) -> None:
        post_id = uuid.uuid4()
        publisher = MockPublisher(Platform.INSTAGRAM)
        r1 = await publisher.publish(
            db=AsyncMock(),
            connection=_fake_connection(),
            post=_fake_post(post_id),
            video_bytes=b"x",
            video_url="x",
        )
        r2 = await publisher.publish(
            db=AsyncMock(),
            connection=_fake_connection(),
            post=_fake_post(post_id),
            video_bytes=b"x",
            video_url="x",
        )
        # Same post id → same platform_post_id (timestamps will differ)
        assert r1.platform_post_id == r2.platform_post_id
        assert r1.published_url == r2.published_url

    async def test_handles_every_platform(self) -> None:
        for platform in Platform:
            publisher = MockPublisher(platform)
            result = await publisher.publish(
                db=AsyncMock(),
                connection=_fake_connection(),
                post=_fake_post(),
                video_bytes=b"",
                video_url="",
            )
            assert platform.value in result.published_url
            assert publisher.platform == platform
