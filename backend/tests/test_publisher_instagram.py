"""Tests for InstagramReelsPublisher — Graph API two-step flow via mocked httpx."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.common.encryption import encrypt_token
from app.platforms.base import Platform
from app.publishing.oauth_providers.base import (
    OAuthProvider,
    TokenExchangeResult,
)
from app.publishing.publishers.base import PublisherError, PublishResult
from app.publishing.publishers.instagram import InstagramReelsPublisher


# ============================================================================
# Helpers
# ============================================================================


def _make_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.json = MagicMock(return_value=json_data)
    resp.status_code = status_code
    resp.text = json.dumps(json_data)
    return resp


def _mock_client_with_responses(
    post_responses: list[MagicMock],
    get_responses: list[MagicMock],
) -> tuple[MagicMock, MagicMock]:
    """Build an httpx mock that returns sequential responses for post/get."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=post_responses)
    mock_client.get = AsyncMock(side_effect=get_responses)

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_client_cls, mock_client


def _connection() -> MagicMock:
    conn = MagicMock()
    conn.id = uuid.uuid4()
    conn.platform = "instagram"
    conn.access_token = encrypt_token("plain-ig-access-token")
    conn.refresh_token = encrypt_token("plain-ig-refresh-token")
    conn.token_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    conn.platform_user_id = "ig_user_999"
    return conn


def _post() -> MagicMock:
    post = MagicMock()
    post.id = uuid.uuid4()
    post.title = "Reels test"
    post.description = "Hello world"
    post.hashtags = ["fitness", "morning"]
    return post


def _oauth() -> MagicMock:
    provider = MagicMock(spec=OAuthProvider)
    provider.platform = Platform.INSTAGRAM
    provider.name = "mock-meta"
    provider.refresh_access_token = AsyncMock(
        return_value=TokenExchangeResult(
            access_token="refreshed-ig-token",
            refresh_token=None,
            expires_in=5184000,  # 60 days
        )
    )
    return provider


def _db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ============================================================================
# Happy path
# ============================================================================


class TestInstagramPublishHappyPath:
    async def test_full_three_step_flow(self) -> None:
        publisher = InstagramReelsPublisher(oauth_provider=_oauth())
        mock_cls, mock_client = _mock_client_with_responses(
            post_responses=[
                _make_response({"id": "container_123"}),  # create container
                _make_response({"id": "ig_post_456"}),  # publish
            ],
            get_responses=[
                _make_response({"status_code": "FINISHED"}),  # status poll
            ],
        )

        with patch(
            "app.publishing.publishers.instagram.httpx.AsyncClient", mock_cls
        ):
            result = await publisher.publish(
                db=_db(),
                connection=_connection(),
                post=_post(),
                video_bytes=b"ignored",
                video_url="https://example.com/v.mp4",
            )

        assert isinstance(result, PublishResult)
        assert result.platform_post_id == "ig_post_456"
        assert "instagram.com" in result.published_url
        assert "ig_post_456" in result.published_url

    async def test_container_creation_includes_video_url_and_caption(self) -> None:
        publisher = InstagramReelsPublisher(oauth_provider=_oauth())
        mock_cls, mock_client = _mock_client_with_responses(
            post_responses=[
                _make_response({"id": "container_123"}),
                _make_response({"id": "ig_post_456"}),
            ],
            get_responses=[_make_response({"status_code": "FINISHED"})],
        )

        with patch(
            "app.publishing.publishers.instagram.httpx.AsyncClient", mock_cls
        ):
            await publisher.publish(
                db=_db(),
                connection=_connection(),
                post=_post(),
                video_bytes=b"x",
                video_url="https://supabase/v.mp4",
            )

        first_post_call = mock_client.post.call_args_list[0]
        sent_data = first_post_call.kwargs["data"]
        assert sent_data["media_type"] == "REELS"
        assert sent_data["video_url"] == "https://supabase/v.mp4"
        assert "Reels test" in sent_data["caption"]
        assert "#fitness" in sent_data["caption"]
        assert "#morning" in sent_data["caption"]
        assert sent_data["access_token"] == "plain-ig-access-token"


# ============================================================================
# Status polling
# ============================================================================


class TestInstagramStatusPolling:
    async def test_polling_waits_for_finished(self) -> None:
        """Container is IN_PROGRESS twice, then FINISHED — publish proceeds."""
        publisher = InstagramReelsPublisher(oauth_provider=_oauth())
        mock_cls, mock_client = _mock_client_with_responses(
            post_responses=[
                _make_response({"id": "container_123"}),
                _make_response({"id": "ig_post_456"}),
            ],
            get_responses=[
                _make_response({"status_code": "IN_PROGRESS"}),
                _make_response({"status_code": "IN_PROGRESS"}),
                _make_response({"status_code": "FINISHED"}),
            ],
        )

        with patch(
            "app.publishing.publishers.instagram.httpx.AsyncClient", mock_cls
        ):
            with patch(
                "app.publishing.publishers.instagram.asyncio.sleep",
                AsyncMock(),
            ):
                result = await publisher.publish(
                    db=_db(),
                    connection=_connection(),
                    post=_post(),
                    video_bytes=b"x",
                    video_url="x",
                )

        assert result.platform_post_id == "ig_post_456"
        assert mock_client.get.call_count == 3

    async def test_polling_raises_on_error_status(self) -> None:
        publisher = InstagramReelsPublisher(oauth_provider=_oauth())
        mock_cls, _ = _mock_client_with_responses(
            post_responses=[_make_response({"id": "container_123"})],
            get_responses=[_make_response({"status_code": "ERROR"})],
        )

        with patch(
            "app.publishing.publishers.instagram.httpx.AsyncClient", mock_cls
        ):
            with patch(
                "app.publishing.publishers.instagram.asyncio.sleep", AsyncMock()
            ):
                with pytest.raises(PublisherError, match="ERROR state"):
                    await publisher.publish(
                        db=_db(),
                        connection=_connection(),
                        post=_post(),
                        video_bytes=b"x",
                        video_url="x",
                    )

    async def test_polling_times_out_after_max(self) -> None:
        """All polls return IN_PROGRESS → timeout error."""
        publisher = InstagramReelsPublisher(oauth_provider=_oauth())
        in_progress = _make_response({"status_code": "IN_PROGRESS"})
        # Enough responses to cover the full timeout
        mock_cls, _ = _mock_client_with_responses(
            post_responses=[_make_response({"id": "container_123"})],
            get_responses=[in_progress] * 100,
        )

        with patch(
            "app.publishing.publishers.instagram.httpx.AsyncClient", mock_cls
        ):
            with patch(
                "app.publishing.publishers.instagram.asyncio.sleep", AsyncMock()
            ):
                with pytest.raises(PublisherError, match="did not finish"):
                    await publisher.publish(
                        db=_db(),
                        connection=_connection(),
                        post=_post(),
                        video_bytes=b"x",
                        video_url="x",
                    )


# ============================================================================
# Errors + token refresh
# ============================================================================


class TestInstagramErrors:
    async def test_missing_platform_user_id_raises(self) -> None:
        publisher = InstagramReelsPublisher(oauth_provider=_oauth())
        conn = _connection()
        conn.platform_user_id = None

        with pytest.raises(PublisherError, match="ig-user-id"):
            await publisher.publish(
                db=_db(),
                connection=conn,
                post=_post(),
                video_bytes=b"x",
                video_url="x",
            )

    async def test_container_creation_400_raises(self) -> None:
        publisher = InstagramReelsPublisher(oauth_provider=_oauth())
        mock_cls, _ = _mock_client_with_responses(
            post_responses=[
                _make_response(
                    {
                        "error": {
                            "message": "video_url not reachable",
                            "code": 100,
                        }
                    },
                    status_code=400,
                )
            ],
            get_responses=[],
        )

        with patch(
            "app.publishing.publishers.instagram.httpx.AsyncClient", mock_cls
        ):
            with pytest.raises(PublisherError, match="not reachable"):
                await publisher.publish(
                    db=_db(),
                    connection=_connection(),
                    post=_post(),
                    video_bytes=b"x",
                    video_url="x",
                )
