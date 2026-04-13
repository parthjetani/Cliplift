"""YouTube Shorts publisher — videos.insert via the YouTube Data API v3.

Hand-rolls the multipart/related upload body so we don't need
`google-api-python-client` (extra dep, extra mocking surface). The REST API
contract is documented at:
    https://developers.google.com/youtube/v3/docs/videos/insert

Activated when there's an OAuth provider that can mint access tokens for
YouTube — in practice that's `YouTubeOAuthProvider` in production and
`MockOAuthProvider` in dev/tests. The publisher itself doesn't gate on env
vars because publish-time auth lives on the connection row, not in settings.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx

from app.platforms.base import Platform
from app.publishing.publishers._credentials import get_fresh_access_token
from app.publishing.publishers.base import (
    Publisher,
    PublisherError,
    PublishResult,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.publishing.models import PlatformConnection, ScheduledPost
    from app.publishing.oauth_providers.base import OAuthProvider

logger = logging.getLogger(__name__)


YOUTUBE_UPLOAD_URL = (
    "https://www.googleapis.com/upload/youtube/v3/videos"
    "?uploadType=multipart&part=snippet,status"
)

# Category 22 = "People & Blogs" — safe default for short-form creator content.
DEFAULT_CATEGORY_ID = "22"


class YouTubeShortsPublisher(Publisher):
    """Pushes a `ScheduledPost` to YouTube as a Short via videos.insert."""

    platform = Platform.YOUTUBE
    name = "youtube_data_api"

    def __init__(self, oauth_provider: "OAuthProvider") -> None:
        self.oauth_provider = oauth_provider

    async def publish(
        self,
        *,
        db: "AsyncSession",
        connection: "PlatformConnection",
        post: "ScheduledPost",
        video_bytes: bytes,
        video_url: str,
    ) -> PublishResult:
        access_token = await get_fresh_access_token(
            db, connection, self.oauth_provider
        )

        body, content_type = self._build_multipart_body(post, video_bytes)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(YOUTUBE_UPLOAD_URL, headers=headers, content=body)

        if resp.status_code != 200:
            logger.error(
                f"YouTube videos.insert failed for post {post.id}: "
                f"{resp.status_code} {resp.text[:500]}"
            )
            raise PublisherError(
                f"YouTube upload failed ({resp.status_code}): "
                f"{self._extract_api_error(resp)}"
            )

        data = resp.json()
        video_id = data.get("id")
        if not video_id:
            raise PublisherError(
                f"YouTube upload returned no video id: {data}"
            )

        return PublishResult(
            platform_post_id=video_id,
            published_url=f"https://youtube.com/shorts/{video_id}",
            published_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_multipart_body(
        self, post: "ScheduledPost", video_bytes: bytes
    ) -> tuple[bytes, str]:
        """Construct a multipart/related body for the videos.insert call.

        Returns (body, Content-Type header value).
        """
        boundary = f"cliplift_{uuid.uuid4().hex}"

        metadata = {
            "snippet": {
                "title": (post.title or "Untitled")[:100],
                "description": post.description or "",
                "tags": post.hashtags or [],
                "categoryId": DEFAULT_CATEGORY_ID,
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }
        metadata_json = json.dumps(metadata).encode("utf-8")

        crlf = b"\r\n"
        boundary_line = f"--{boundary}".encode()
        end_boundary = f"--{boundary}--".encode()

        body = b"".join(
            [
                boundary_line, crlf,
                b"Content-Type: application/json; charset=UTF-8", crlf, crlf,
                metadata_json, crlf,
                boundary_line, crlf,
                b"Content-Type: video/mp4", crlf, crlf,
                video_bytes, crlf,
                end_boundary, crlf,
            ]
        )

        return body, f"multipart/related; boundary={boundary}"

    @staticmethod
    def _extract_api_error(resp: httpx.Response) -> str:
        """Best-effort extraction of the human-readable error from a YT error body."""
        try:
            payload = resp.json()
            err = payload.get("error", {})
            return err.get("message") or str(err)[:200]
        except (ValueError, KeyError):
            return resp.text[:200]
