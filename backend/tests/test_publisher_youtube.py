"""Tests for YouTubeShortsPublisher — videos.insert via mocked httpx."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.common.encryption import decrypt_token, encrypt_token
from app.platforms.base import Platform
from app.publishing.oauth_providers.base import (
    OAuthProvider,
    TokenExchangeResult,
)
from app.publishing.publishers.base import PublisherError, PublishResult
from app.publishing.publishers.youtube import YouTubeShortsPublisher


# ============================================================================
# Helpers
# ============================================================================


def _mock_httpx_client(
    json_response: dict | None = None,
    status_code: int = 200,
    text: str = "",
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build an httpx.AsyncClient mock whose .post() returns json_response."""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json = MagicMock(return_value=json_response or {})
    mock_resp.status_code = status_code
    mock_resp.text = text or json.dumps(json_response or {})
    mock_resp.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.get = AsyncMock(return_value=mock_resp)

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_client_cls, mock_client, mock_resp


def _fresh_connection() -> MagicMock:
    """Connection with a non-expired access token."""
    conn = MagicMock()
    conn.id = uuid.uuid4()
    conn.platform = "youtube"
    conn.access_token = encrypt_token("plain-access-token")
    conn.refresh_token = encrypt_token("plain-refresh-token")
    conn.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    conn.platform_user_id = "yt-user-123"
    return conn


def _expired_connection() -> MagicMock:
    conn = _fresh_connection()
    conn.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    return conn


def _fake_post() -> MagicMock:
    post = MagicMock()
    post.id = uuid.uuid4()
    post.title = "Test Short"
    post.description = "A description"
    post.hashtags = ["fitness", "morning"]
    return post


def _fake_oauth_provider(
    *, refresh_result: TokenExchangeResult | None = None
) -> MagicMock:
    """Mock OAuth provider with a stubbable refresh_access_token."""
    provider = MagicMock(spec=OAuthProvider)
    provider.platform = Platform.YOUTUBE
    provider.name = "mock-oauth"
    provider.refresh_access_token = AsyncMock(
        return_value=refresh_result
        or TokenExchangeResult(
            access_token="refreshed-access-token",
            refresh_token="rotated-refresh-token",
            expires_in=3600,
        )
    )
    return provider


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ============================================================================
# Happy path
# ============================================================================


class TestYouTubePublishHappyPath:
    async def test_publish_returns_video_id(self) -> None:
        publisher = YouTubeShortsPublisher(oauth_provider=_fake_oauth_provider())
        mock_cls, mock_client, _ = _mock_httpx_client(
            json_response={"id": "yt_vid_xyz", "kind": "youtube#video"}
        )

        with patch("app.publishing.publishers.youtube.httpx.AsyncClient", mock_cls):
            result = await publisher.publish(
                db=_mock_db(),
                connection=_fresh_connection(),
                post=_fake_post(),
                video_bytes=b"video bytes here",
                video_url="https://example.com/v.mp4",
            )

        assert isinstance(result, PublishResult)
        assert result.platform_post_id == "yt_vid_xyz"
        assert result.published_url == "https://youtube.com/shorts/yt_vid_xyz"
        assert mock_client.post.call_count == 1

    async def test_multipart_body_contains_metadata_and_bytes(self) -> None:
        publisher = YouTubeShortsPublisher(oauth_provider=_fake_oauth_provider())
        mock_cls, mock_client, _ = _mock_httpx_client(
            json_response={"id": "yt_vid_xyz"}
        )

        post = _fake_post()
        with patch("app.publishing.publishers.youtube.httpx.AsyncClient", mock_cls):
            await publisher.publish(
                db=_mock_db(),
                connection=_fresh_connection(),
                post=post,
                video_bytes=b"VIDEO_BYTES_MARKER",
                video_url="https://example.com/v.mp4",
            )

        call_kwargs = mock_client.post.call_args.kwargs
        body = call_kwargs["content"]
        headers = call_kwargs["headers"]
        assert b"VIDEO_BYTES_MARKER" in body
        # snippet should include the title + tags
        assert post.title.encode() in body
        assert b"fitness" in body
        assert b"morning" in body
        assert b"categoryId" in body
        # multipart content type with boundary
        assert headers["Content-Type"].startswith("multipart/related; boundary=")
        assert headers["Authorization"] == "Bearer plain-access-token"

    async def test_url_uses_shorts_format(self) -> None:
        publisher = YouTubeShortsPublisher(oauth_provider=_fake_oauth_provider())
        mock_cls, _, _ = _mock_httpx_client(json_response={"id": "abc123"})
        with patch("app.publishing.publishers.youtube.httpx.AsyncClient", mock_cls):
            result = await publisher.publish(
                db=_mock_db(),
                connection=_fresh_connection(),
                post=_fake_post(),
                video_bytes=b"x",
                video_url="x",
            )
        assert result.published_url == "https://youtube.com/shorts/abc123"


# ============================================================================
# Token refresh path
# ============================================================================


class TestYouTubeTokenRefresh:
    async def test_expired_token_triggers_refresh(self) -> None:
        oauth = _fake_oauth_provider()
        publisher = YouTubeShortsPublisher(oauth_provider=oauth)
        mock_cls, mock_client, _ = _mock_httpx_client(
            json_response={"id": "yt_vid_xyz"}
        )

        conn = _expired_connection()
        db = _mock_db()
        with patch("app.publishing.publishers.youtube.httpx.AsyncClient", mock_cls):
            await publisher.publish(
                db=db,
                connection=conn,
                post=_fake_post(),
                video_bytes=b"x",
                video_url="x",
            )

        # OAuth refresh was called with the decrypted refresh token
        oauth.refresh_access_token.assert_awaited_once_with("plain-refresh-token")
        # Connection was persisted (encrypted access token replaced)
        assert db.add.called
        assert db.commit.await_count == 1
        # The new token is encrypted but should decrypt to the refreshed value
        assert decrypt_token(conn.access_token) == "refreshed-access-token"
        # The Authorization header on the upload uses the *new* plaintext token
        sent_headers = mock_client.post.call_args.kwargs["headers"]
        assert sent_headers["Authorization"] == "Bearer refreshed-access-token"

    async def test_fresh_token_skips_refresh(self) -> None:
        oauth = _fake_oauth_provider()
        publisher = YouTubeShortsPublisher(oauth_provider=oauth)
        mock_cls, _, _ = _mock_httpx_client(json_response={"id": "x"})

        with patch("app.publishing.publishers.youtube.httpx.AsyncClient", mock_cls):
            await publisher.publish(
                db=_mock_db(),
                connection=_fresh_connection(),
                post=_fake_post(),
                video_bytes=b"x",
                video_url="x",
            )

        oauth.refresh_access_token.assert_not_called()


# ============================================================================
# Error handling
# ============================================================================


class TestYouTubeErrors:
    async def test_400_response_raises_publisher_error(self) -> None:
        publisher = YouTubeShortsPublisher(oauth_provider=_fake_oauth_provider())
        mock_cls, _, _ = _mock_httpx_client(
            json_response={
                "error": {
                    "code": 400,
                    "message": "Invalid video format",
                }
            },
            status_code=400,
        )

        with patch("app.publishing.publishers.youtube.httpx.AsyncClient", mock_cls):
            with pytest.raises(PublisherError, match="Invalid video format"):
                await publisher.publish(
                    db=_mock_db(),
                    connection=_fresh_connection(),
                    post=_fake_post(),
                    video_bytes=b"x",
                    video_url="x",
                )

    async def test_missing_id_in_response_raises(self) -> None:
        publisher = YouTubeShortsPublisher(oauth_provider=_fake_oauth_provider())
        mock_cls, _, _ = _mock_httpx_client(json_response={"kind": "youtube#video"})

        with patch("app.publishing.publishers.youtube.httpx.AsyncClient", mock_cls):
            with pytest.raises(PublisherError, match="no video id"):
                await publisher.publish(
                    db=_mock_db(),
                    connection=_fresh_connection(),
                    post=_fake_post(),
                    video_bytes=b"x",
                    video_url="x",
                )
