"""Tests for the publish-scheduled worker.

These run end-to-end against the real DB + real LocalStorageBackend + a
PublisherRouter wired with controlled publishers (mostly `MockPublisher`,
plus a small `RaisingPublisher` for the failure paths).

Setup goes through the HTTP API (signup → mock OAuth → CRUD) so we get
real auth.users / profiles / teams / platform_connections rows. The worker
itself is invoked directly with an AsyncSessionLocal session — no HTTP — so
the assertions can poke at the DB without going through the API layer.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.common.storage import LocalStorageBackend
from app.database import AsyncSessionLocal, engine
from app.platforms.base import Platform
from app.publishing.models import ScheduledPost
from app.publishing.publisher_router import PublisherRouter
from app.publishing.publishers.base import Publisher, PublisherError, PublishResult
from app.publishing.publishers.mock import MockPublisher
from app.workers.publish_scheduled import publish_scheduled
from tests.test_creators import _create_real_user, _upgrade_team_plan

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.publishing.models import PlatformConnection


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def db_session() -> AsyncGenerator["AsyncSession", None]:
    """A direct AsyncSession for tests that bypass the HTTP layer.

    Mirrors the conftest `client` fixture's teardown — disposes the engine
    after each test so the next test (which gets a new event loop) doesn't
    try to reuse asyncpg connections from the previous loop.

    Also clears stale `scheduled` posts from prior test runs so the worker
    tests don't accidentally pick up ghost rows. Without this, every test run
    accumulates more posts and eventually the `test_returns_zero_summary` test
    fails because the worker processes stale posts instead of returning zero.
    """
    async with AsyncSessionLocal() as session:
        # Clear stale scheduled posts from prior runs
        await session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.status == "scheduled")
            .values(status="draft")
        )
        await session.commit()
        try:
            yield session
        finally:
            await session.close()
    await engine.dispose()


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(
        root_dir=tmp_path,
        public_base_url="http://localhost:8000",
    )


@pytest.fixture
def mock_publisher_router() -> PublisherRouter:
    """A router where every platform returns a MockPublisher."""
    router = PublisherRouter()
    for platform in Platform:
        router.register(MockPublisher(platform))
    return router


# ============================================================================
# Test publishers (used by failure-path tests)
# ============================================================================


class RaisingPublisher(Publisher):
    """Publisher that always raises — proves the failure path."""

    name = "raising"

    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    async def publish(
        self,
        *,
        db,
        connection,
        post,
        video_bytes,
        video_url,
    ) -> PublishResult:
        raise PublisherError("simulated publish failure")


# ============================================================================
# Helpers
# ============================================================================


async def _connect_youtube(client: AsyncClient, headers: dict) -> str:
    """Run the mock OAuth flow → return new connection_id."""
    await _upgrade_team_plan(client, headers, "team")  # Creator tier blocks scheduling
    auth_resp = await client.post(
        "/api/v1/connections/youtube/authorize", headers=headers
    )
    callback_url = auth_resp.json()["authorize_url"]
    parsed = urlparse(callback_url)
    await client.get(parsed.path + "?" + parsed.query, follow_redirects=False)

    list_resp = await client.get("/api/v1/connections", headers=headers)
    youtube_conns = [c for c in list_resp.json() if c["platform"] == "youtube"]
    return youtube_conns[-1]["id"]


async def _create_post_via_api(
    client: AsyncClient, headers: dict, *, file_key: str
) -> uuid.UUID:
    """Create a scheduled post via HTTP and return its UUID."""
    conn_id = await _connect_youtube(client, headers)
    payload = {
        "connection_id": conn_id,
        "platform": "youtube",
        "file_key": file_key,
        "title": "worker test post",
        "description": "from test_publish_worker",
        "hashtags": ["test"],
        "scheduled_for": (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat(),
    }
    resp = await client.post(
        "/api/v1/publishing/scheduled-posts", json=payload, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["id"])


async def _set_due_now(
    db: "AsyncSession", post_id: uuid.UUID, *, status: str = "scheduled"
) -> None:
    """Force a post into a state the worker would pick up."""
    await db.execute(
        update(ScheduledPost)
        .where(ScheduledPost.id == post_id)
        .values(
            scheduled_for=datetime.now(timezone.utc) - timedelta(seconds=10),
            status=status,
        )
    )
    await db.commit()


async def _get_post(db: "AsyncSession", post_id: uuid.UUID) -> ScheduledPost:
    result = await db.execute(
        select(ScheduledPost).where(ScheduledPost.id == post_id)
    )
    return result.scalar_one()


async def _seed_one_due_post(
    client: AsyncClient,
    db: "AsyncSession",
    storage: LocalStorageBackend,
    *,
    file_bytes: bytes = b"video bytes",
    write_file: bool = True,
) -> tuple[uuid.UUID, dict]:
    """Sign up a user, connect YouTube, create a post, mark it due, write the file.

    Returns (post_id, headers) — headers in case the test wants to make more API calls.
    """
    user_id, _, token = await _create_real_user()
    headers = {"Authorization": f"Bearer {token}"}

    file_key = f"{user_id}/{uuid.uuid4()}/test.mp4"
    if write_file:
        await storage.write_bytes(file_key, file_bytes)

    post_id = await _create_post_via_api(client, headers, file_key=file_key)
    await _set_due_now(db, post_id)
    return post_id, headers


# ============================================================================
# Empty + status guards
# ============================================================================


class TestNoDuePosts:
    async def test_returns_zero_summary(
        self,
        db_session: "AsyncSession",
        storage: LocalStorageBackend,
        mock_publisher_router: PublisherRouter,
    ) -> None:
        """No due posts → worker returns clean zero summary."""
        summary = await publish_scheduled(
            db_session, storage, mock_publisher_router, max_posts=5
        )
        assert summary["processed"] == 0
        assert summary["succeeded"] == 0
        assert summary["failed"] == 0
        assert summary["errors"] == []


class TestStatusGuards:
    async def test_draft_post_not_picked_up(
        self,
        client: AsyncClient,
        db_session: "AsyncSession",
        storage: LocalStorageBackend,
        mock_publisher_router: PublisherRouter,
    ) -> None:
        post_id, _ = await _seed_one_due_post(client, db_session, storage)
        # Override status to draft (still in the past, but wrong status)
        await _set_due_now(db_session, post_id, status="draft")

        summary = await publish_scheduled(
            db_session, storage, mock_publisher_router
        )
        assert summary["processed"] == 0

        post = await _get_post(db_session, post_id)
        assert post.status == "draft"

    async def test_publishing_post_not_picked_up(
        self,
        client: AsyncClient,
        db_session: "AsyncSession",
        storage: LocalStorageBackend,
        mock_publisher_router: PublisherRouter,
    ) -> None:
        """A post already in `publishing` (e.g., from a crashed prior worker) is not re-picked."""
        post_id, _ = await _seed_one_due_post(client, db_session, storage)
        await _set_due_now(db_session, post_id, status="publishing")

        summary = await publish_scheduled(
            db_session, storage, mock_publisher_router
        )
        assert summary["processed"] == 0

    async def test_future_scheduled_for_not_picked_up(
        self,
        client: AsyncClient,
        db_session: "AsyncSession",
        storage: LocalStorageBackend,
        mock_publisher_router: PublisherRouter,
    ) -> None:
        post_id, _ = await _seed_one_due_post(client, db_session, storage)
        # Override scheduled_for to 1 hour in the future
        await db_session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.id == post_id)
            .values(
                scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
                status="scheduled",
            )
        )
        await db_session.commit()

        summary = await publish_scheduled(
            db_session, storage, mock_publisher_router
        )
        assert summary["processed"] == 0


# ============================================================================
# Happy path
# ============================================================================


class TestPublishSuccess:
    async def test_publishes_due_post(
        self,
        client: AsyncClient,
        db_session: "AsyncSession",
        storage: LocalStorageBackend,
        mock_publisher_router: PublisherRouter,
    ) -> None:
        post_id, _ = await _seed_one_due_post(client, db_session, storage)

        summary = await publish_scheduled(
            db_session, storage, mock_publisher_router
        )
        assert summary["processed"] == 1
        assert summary["succeeded"] == 1
        assert summary["failed"] == 0

        post = await _get_post(db_session, post_id)
        assert post.status == "published"
        assert post.platform_post_id.startswith("mock_")
        assert post.media_url is not None
        assert "youtube" in post.media_url
        assert post.published_at is not None
        assert post.error_message is None


# ============================================================================
# Failure path
# ============================================================================


class TestPublishFailure:
    async def test_publisher_error_marks_failed(
        self,
        client: AsyncClient,
        db_session: "AsyncSession",
        storage: LocalStorageBackend,
    ) -> None:
        """Publisher raises → row goes to `failed` with the error message."""
        # Router with a raising publisher for YouTube
        router = PublisherRouter()
        router.register(RaisingPublisher(Platform.YOUTUBE))
        for p in (Platform.INSTAGRAM, Platform.LINKEDIN, Platform.TIKTOK):
            router.register(MockPublisher(p))

        post_id, _ = await _seed_one_due_post(client, db_session, storage)

        summary = await publish_scheduled(db_session, storage, router)
        assert summary["processed"] == 1
        assert summary["succeeded"] == 0
        assert summary["failed"] == 1
        assert len(summary["errors"]) == 1
        assert "simulated publish failure" in summary["errors"][0]["error"]

        post = await _get_post(db_session, post_id)
        assert post.status == "failed"
        assert "simulated publish failure" in (post.error_message or "")
        # platform_post_id should remain unset
        assert post.platform_post_id is None

    async def test_storage_missing_file_marks_failed(
        self,
        client: AsyncClient,
        db_session: "AsyncSession",
        storage: LocalStorageBackend,
        mock_publisher_router: PublisherRouter,
    ) -> None:
        """File never written → storage.download_bytes raises → post marked failed."""
        post_id, _ = await _seed_one_due_post(
            client, db_session, storage, write_file=False
        )

        summary = await publish_scheduled(
            db_session, storage, mock_publisher_router
        )
        assert summary["failed"] == 1

        post = await _get_post(db_session, post_id)
        assert post.status == "failed"
        assert "FileNotFoundError" in (post.error_message or "")


# ============================================================================
# SKIP LOCKED — concurrent worker pickup
# ============================================================================


class TestSkipLockedConcurrency:
    async def test_two_workers_pick_different_posts(
        self,
        client: AsyncClient,
        storage: LocalStorageBackend,
        mock_publisher_router: PublisherRouter,
    ) -> None:
        """Two concurrent workers must pick *different* posts (SKIP LOCKED proof).

        Uses two separate AsyncSessionLocal sessions so the row-level locks
        actually behave concurrently. With a single session there's no race
        because only one connection holds the lock.
        """
        # Seed two due posts (same user, two different posts via two connections)
        async with AsyncSessionLocal() as setup_session:
            post_a_id, headers_a = await _seed_one_due_post(
                client, setup_session, storage, file_bytes=b"a"
            )
            post_b_id, headers_b = await _seed_one_due_post(
                client, setup_session, storage, file_bytes=b"b"
            )

        # Two parallel worker invocations, each with its own session
        async def run_worker() -> dict:
            async with AsyncSessionLocal() as s:
                return await publish_scheduled(
                    s, storage, mock_publisher_router, max_posts=1
                )

        results = await asyncio.gather(run_worker(), run_worker())

        # Combined: both posts processed exactly once across the two workers
        total_processed = sum(r["processed"] for r in results)
        total_succeeded = sum(r["succeeded"] for r in results)
        assert total_processed == 2
        assert total_succeeded == 2

        # Both posts should now be published
        async with AsyncSessionLocal() as s:
            post_a = await _get_post(s, post_a_id)
            post_b = await _get_post(s, post_b_id)
        assert post_a.status == "published"
        assert post_b.status == "published"
        assert post_a.platform_post_id != post_b.platform_post_id
