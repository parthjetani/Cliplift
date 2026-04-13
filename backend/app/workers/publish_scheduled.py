"""Worker that publishes due ScheduledPost rows.

Triggered by QStash on a 5-minute cron in production. The HTTP route is
`POST /api/v1/workers/publish-scheduled` (registered in `workers/routes.py`).

Concurrency model
-----------------
1. `SELECT FOR UPDATE SKIP LOCKED` picks up to N due posts atomically.
2. Status flips to `publishing` immediately and the transaction commits —
   this releases the row locks but the new status keeps other worker
   instances from re-picking the same posts.
3. Each post is then processed in its own try/except. On failure, the
   session is rolled back and the post is re-fetched + marked `failed`
   with the error message, so a half-broken session never leaves a post
   stuck in `publishing` forever.

Worker stays alive across individual post failures — partial success is
better than aborting the whole batch.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.storage import StorageBackend
from app.platforms.base import Platform
from app.publishing.models import PlatformConnection, ScheduledPost
from app.publishing.publisher_router import PublisherRouter
from app.publishing.publishers.base import PublisherError
from app.publishing.schemas import PostStatus

logger = logging.getLogger(__name__)


async def publish_scheduled(
    db: AsyncSession,
    storage: StorageBackend,
    publisher_router: PublisherRouter,
    *,
    max_posts: int = 1,
) -> dict:
    """Pick up to `max_posts` due posts and publish them.

    Returns a summary dict with `processed`, `succeeded`, `failed`, and a
    list of errors. The endpoint always returns 200 — failures are reported
    in the body, never raised, because we want the worker to keep going on
    the next post and the next QStash trigger.
    """
    post_ids = await _pick_and_lock_due_posts(db, max_posts)

    summary: dict = {
        "processed": len(post_ids),
        "succeeded": 0,
        "failed": 0,
        "errors": [],
    }

    for post_id in post_ids:
        try:
            await _publish_one(db, storage, publisher_router, post_id)
            summary["succeeded"] += 1
        except Exception as e:
            await db.rollback()
            error_msg = f"{type(e).__name__}: {e}"
            logger.exception(f"Publish failed for post {post_id}")
            await _mark_failed(db, post_id, error_msg)
            summary["failed"] += 1
            summary["errors"].append(
                {"post_id": str(post_id), "error": error_msg[:500]}
            )

    return summary


# ----------------------------------------------------------------------------
# Step 1: pick + lock due posts atomically
# ----------------------------------------------------------------------------


async def _pick_and_lock_due_posts(
    db: AsyncSession, max_posts: int
) -> list[uuid.UUID]:
    """`SELECT FOR UPDATE SKIP LOCKED` then flip status → publishing.

    Returns the list of post IDs we successfully claimed. Other concurrent
    workers will not see these posts as `scheduled` after this function
    commits, so they can't double-pick.
    """
    now = datetime.now(timezone.utc)
    query = (
        select(ScheduledPost)
        .where(
            ScheduledPost.status == PostStatus.SCHEDULED.value,
            ScheduledPost.scheduled_for <= now,
        )
        .order_by(ScheduledPost.scheduled_for.asc())
        .limit(max_posts)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(query)
    posts = list(result.scalars().all())

    post_ids: list[uuid.UUID] = []
    for post in posts:
        post.status = PostStatus.PUBLISHING.value
        post_ids.append(post.id)

    await db.commit()
    return post_ids


# ----------------------------------------------------------------------------
# Step 2: process one post
# ----------------------------------------------------------------------------


async def _publish_one(
    db: AsyncSession,
    storage: StorageBackend,
    publisher_router: PublisherRouter,
    post_id: uuid.UUID,
) -> None:
    """Download bytes, dispatch to the publisher, write success state.

    Raises on any error — caller catches and marks the post failed.
    """
    post = await _get_post(db, post_id)
    if not post:
        raise PublisherError(f"Post {post_id} disappeared mid-batch")

    if not post.file_key:
        raise PublisherError(f"Post {post_id} has no file_key")

    # Resolve the publisher up front so a misconfigured platform fails fast.
    try:
        platform = Platform(post.platform)
    except ValueError as e:
        raise PublisherError(f"Unknown platform '{post.platform}'") from e

    publisher = publisher_router.get(platform)
    if not publisher:
        raise PublisherError(f"No publisher registered for {platform.value}")

    # Load the OAuth connection (encrypted tokens — publisher decrypts itself).
    connection = await _get_connection(db, post.connection_id)
    if not connection:
        raise PublisherError(
            f"Connection {post.connection_id} not found for post {post_id}"
        )

    # Pull the bytes and a public URL — publishers use one or the other.
    video_bytes = await storage.download_bytes(post.file_key)
    video_url = await storage.create_download_url(post.file_key, expires_in=3600)

    result = await publisher.publish(
        db=db,
        connection=connection,
        post=post,
        video_bytes=video_bytes,
        video_url=video_url,
    )

    # Re-fetch the post in case the publisher's token-refresh commit detached
    # our reference (it shouldn't, but defensive).
    post = await _get_post(db, post_id)
    if post is None:
        raise PublisherError(
            f"Post {post_id} vanished after publish — refusing to leave it stale"
        )
    post.status = PostStatus.PUBLISHED.value
    post.platform_post_id = result.platform_post_id
    post.media_url = result.published_url
    post.published_at = result.published_at
    post.error_message = None
    await db.commit()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


async def _get_post(db: AsyncSession, post_id: uuid.UUID) -> ScheduledPost | None:
    result = await db.execute(
        select(ScheduledPost).where(ScheduledPost.id == post_id)
    )
    return result.scalar_one_or_none()


async def _get_connection(
    db: AsyncSession, connection_id: uuid.UUID
) -> PlatformConnection | None:
    result = await db.execute(
        select(PlatformConnection).where(PlatformConnection.id == connection_id)
    )
    return result.scalar_one_or_none()


async def _mark_failed(
    db: AsyncSession, post_id: uuid.UUID, error_message: str
) -> None:
    """Set a post's status to `failed` after a processing error.

    Runs in a fresh transaction (the caller has already rolled back) so it's
    safe even if the previous attempt left the session in a weird state.
    """
    try:
        post = await _get_post(db, post_id)
        if post is None:
            logger.error(
                f"_mark_failed: post {post_id} not found, can't mark failed"
            )
            return
        post.status = PostStatus.FAILED.value
        post.error_message = error_message[:1000]
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to mark post {post_id} as failed: {e}")
