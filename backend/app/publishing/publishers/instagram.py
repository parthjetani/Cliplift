"""Instagram Reels publisher — Meta Graph API two-step container flow.

Reels are published via the standard Instagram Graph Content Publishing API:

    1. POST /{ig-user-id}/media         (media_type=REELS, video_url, caption)
       → returns { id: container_id }

    2. GET  /{container_id}?fields=status_code      (poll until FINISHED)
       → status_code transitions IN_PROGRESS → FINISHED (or ERROR)

    3. POST /{ig-user-id}/media_publish (creation_id=container_id)
       → returns { id: post_id }

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing

The Graph API fetches the video itself from `video_url`, so this publisher
ignores `video_bytes` entirely. The worker is responsible for handing us a
publicly-accessible URL — in production that's a Supabase Storage signed URL
with at least an hour of lifetime; in dev/tests it's a mock URL.
"""

from __future__ import annotations

import asyncio
import logging
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


GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

# How long to poll the container status before giving up.
# Most Reels finish processing in <20s; allow up to 90s for safety.
CONTAINER_POLL_TIMEOUT_SECONDS = 90
CONTAINER_POLL_INTERVAL_SECONDS = 5


class InstagramReelsPublisher(Publisher):
    """Pushes a `ScheduledPost` to Instagram Reels via the Graph API."""

    platform = Platform.INSTAGRAM
    name = "meta_graph_api"

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
        if not connection.platform_user_id:
            raise PublisherError(
                f"Instagram connection {connection.id} has no platform_user_id "
                f"(ig-user-id) — user must reconnect"
            )

        access_token = await get_fresh_access_token(
            db, connection, self.oauth_provider
        )
        ig_user_id = connection.platform_user_id
        caption = self._build_caption(post)

        async with httpx.AsyncClient(timeout=30.0) as client:
            container_id = await self._create_container(
                client, ig_user_id, access_token, video_url, caption
            )
            await self._wait_for_container_ready(
                client, container_id, access_token
            )
            ig_post_id = await self._publish_container(
                client, ig_user_id, container_id, access_token
            )

        return PublishResult(
            platform_post_id=ig_post_id,
            published_url=f"https://www.instagram.com/p/{ig_post_id}/",
            published_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_caption(post: "ScheduledPost") -> str:
        """Compose the caption from title + description + hashtags."""
        parts: list[str] = []
        if post.title:
            parts.append(post.title)
        if post.description:
            parts.append(post.description)
        if post.hashtags:
            parts.append(" ".join(f"#{h.lstrip('#')}" for h in post.hashtags))
        return "\n\n".join(parts)

    async def _create_container(
        self,
        client: httpx.AsyncClient,
        ig_user_id: str,
        access_token: str,
        video_url: str,
        caption: str,
    ) -> str:
        """Step 1 — POST /{ig-user-id}/media → returns container id."""
        url = f"{GRAPH_API_BASE}/{ig_user_id}/media"
        resp = await client.post(
            url,
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": access_token,
            },
        )
        if resp.status_code != 200:
            raise PublisherError(
                f"Instagram container creation failed ({resp.status_code}): "
                f"{self._extract_api_error(resp)}"
            )
        data = resp.json()
        container_id = data.get("id")
        if not container_id:
            raise PublisherError(
                f"Instagram container creation returned no id: {data}"
            )
        return container_id

    async def _wait_for_container_ready(
        self,
        client: httpx.AsyncClient,
        container_id: str,
        access_token: str,
    ) -> None:
        """Step 2 — poll /{container_id}?fields=status_code until FINISHED."""
        url = f"{GRAPH_API_BASE}/{container_id}"
        elapsed = 0
        while elapsed < CONTAINER_POLL_TIMEOUT_SECONDS:
            resp = await client.get(
                url,
                params={
                    "fields": "status_code",
                    "access_token": access_token,
                },
            )
            if resp.status_code != 200:
                raise PublisherError(
                    f"Instagram container status check failed "
                    f"({resp.status_code}): {self._extract_api_error(resp)}"
                )
            status_code = resp.json().get("status_code")
            if status_code == "FINISHED":
                return
            if status_code == "ERROR":
                raise PublisherError(
                    f"Instagram container {container_id} entered ERROR state"
                )
            await asyncio.sleep(CONTAINER_POLL_INTERVAL_SECONDS)
            elapsed += CONTAINER_POLL_INTERVAL_SECONDS

        raise PublisherError(
            f"Instagram container {container_id} did not finish processing "
            f"within {CONTAINER_POLL_TIMEOUT_SECONDS}s — try again later"
        )

    async def _publish_container(
        self,
        client: httpx.AsyncClient,
        ig_user_id: str,
        container_id: str,
        access_token: str,
    ) -> str:
        """Step 3 — POST /{ig-user-id}/media_publish → returns post id."""
        url = f"{GRAPH_API_BASE}/{ig_user_id}/media_publish"
        resp = await client.post(
            url,
            data={
                "creation_id": container_id,
                "access_token": access_token,
            },
        )
        if resp.status_code != 200:
            raise PublisherError(
                f"Instagram publish failed ({resp.status_code}): "
                f"{self._extract_api_error(resp)}"
            )
        data = resp.json()
        post_id = data.get("id")
        if not post_id:
            raise PublisherError(
                f"Instagram publish returned no post id: {data}"
            )
        return post_id

    @staticmethod
    def _extract_api_error(resp: httpx.Response) -> str:
        try:
            payload = resp.json()
            err = payload.get("error", {})
            return err.get("message") or str(err)[:200]
        except (ValueError, KeyError):
            return resp.text[:200]
