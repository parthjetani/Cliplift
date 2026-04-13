"""Abstract Publisher interface and shared schemas.

Every publisher (YouTube, Instagram, Mock) implements this interface so the
publish worker can stay platform-agnostic — it just calls
`publisher_router.get(post.platform).publish(...)` and writes the result
back to the `scheduled_posts` row.

Symmetry note: this is the *write* side of the same abstraction `app.platforms`
provides on the *read* side. `DataProvider` reads from a platform; `Publisher`
writes to one. Same shape: ABC + concrete impls + factory + router.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.platforms.base import Platform

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.publishing.models import PlatformConnection, ScheduledPost


class PublishResult(BaseModel):
    """Normalized response from any publisher's `publish()` call.

    Maps cleanly onto the `scheduled_posts` row that the worker is updating —
    when the worker writes the result, the fields line up 1:1.
    """

    model_config = ConfigDict(extra="forbid")

    platform_post_id: str
    published_url: str
    published_at: datetime


class PublisherError(Exception):
    """Raised by a publisher when publishing fails for a recoverable reason.

    The worker catches this, marks the post `failed`, and stores the message
    in `error_message` so the user can see it on the post detail page.
    """


class Publisher(ABC):
    """Abstract base for platform publishers.

    Subclasses set:
        platform: Platform   # which platform this publisher serves
        name: str            # implementation name (e.g., "youtube_data_api", "mock")

    The publish worker passes both `video_bytes` and `video_url`:
    - `video_bytes` is the raw file content (downloaded from storage by the
      worker) — used by publishers that POST binary data (YouTube).
    - `video_url` is a presigned download URL the platform can fetch from —
      used by publishers whose API expects a URL (Instagram Reels).

    Each concrete publisher uses whichever it needs and ignores the other.
    """

    platform: Platform
    name: str

    @abstractmethod
    async def publish(
        self,
        *,
        db: "AsyncSession",
        connection: "PlatformConnection",
        post: "ScheduledPost",
        video_bytes: bytes,
        video_url: str,
    ) -> PublishResult:
        """Publish a scheduled post to the platform.

        Args:
            db: Async session — used by publishers that need to persist
                refreshed OAuth tokens back to the connection row.
            connection: The PlatformConnection (with encrypted tokens) the
                worker resolved by post.connection_id. Publishers decrypt the
                tokens via `app.common.encryption.decrypt_token` and refresh
                them inline if expired.
            post: The ScheduledPost row being published. Title, description,
                hashtags, etc. come from here.
            video_bytes: Raw file bytes (for binary upload publishers).
            video_url: Presigned download URL (for URL-fetch publishers).

        Returns:
            A PublishResult with the platform_post_id and a public URL.

        Raises:
            PublisherError: On any failure the worker should report to the user.
        """

    async def close(self) -> None:
        """Cleanup hook (close HTTP clients, etc.). Override if needed."""
        return None
