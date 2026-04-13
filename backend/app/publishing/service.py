"""Publishing service — presign helper + scheduled-post CRUD.

Routes call into here; this module owns the DB queries and the business
rules (status transitions, ownership checks, file cleanup on delete).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Profile, Team
from app.common.pagination import PaginatedResponse, paginate
from app.common.storage import StorageBackend
from app.dependencies import PaginationParams
from app.platforms.base import Platform
from app.publishing.models import PlatformConnection, ScheduledPost
from app.publishing.schemas import (
    PostStatus,
    PresignRequest,
    PresignResponse,
    ScheduledPostCreate,
    ScheduledPostResponse,
    ScheduledPostUpdate,
)
from app.videos.models import Video

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Status rules
# ----------------------------------------------------------------------------


# A post can be edited (PATCH or DELETE-then-create) only in these states.
# `publishing` and `published` are locked — once the worker picks up a post,
# its content cannot change.
EDITABLE_STATUSES: frozenset[PostStatus] = frozenset(
    {PostStatus.DRAFT, PostStatus.SCHEDULED, PostStatus.FAILED}
)

# Allowed transitions when a client PATCHes the `status` field.
# Worker-driven transitions (scheduled→publishing→published/failed) are not
# represented here — those happen in the worker, not the API.
ALLOWED_STATUS_TRANSITIONS: dict[PostStatus, frozenset[PostStatus]] = {
    PostStatus.DRAFT: frozenset({PostStatus.SCHEDULED}),
    PostStatus.SCHEDULED: frozenset({PostStatus.DRAFT}),
    PostStatus.FAILED: frozenset({PostStatus.SCHEDULED, PostStatus.DRAFT}),
}


def _initial_status(scheduled_for: datetime) -> PostStatus:
    """Posts with a future scheduled_for go straight to `scheduled`; past → `draft`."""
    now = datetime.now(timezone.utc)
    # Make scheduled_for timezone-aware if it isn't
    if scheduled_for.tzinfo is None:
        scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
    return PostStatus.SCHEDULED if scheduled_for > now else PostStatus.DRAFT


# ----------------------------------------------------------------------------
# Presign
# ----------------------------------------------------------------------------


async def presign_upload(
    storage: StorageBackend,
    team: Team,
    payload: PresignRequest,
    expires_in: int = 600,
) -> PresignResponse:
    """Generate a presigned upload URL for the team to PUT a video to.

    The `file_key` is namespaced by team_id so a malicious client cannot guess
    or overwrite another team's files.
    """
    file_key = f"{team.id}/{uuid.uuid4()}/{payload.filename}"
    upload_url = await storage.create_upload_url(
        file_key=file_key,
        content_type=payload.content_type,
        expires_in=expires_in,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return PresignResponse(
        upload_url=upload_url,
        file_key=file_key,
        expires_at=expires_at,
    )


# ----------------------------------------------------------------------------
# Scheduled post CRUD — internal helpers
# ----------------------------------------------------------------------------


async def _get_post_or_404(
    db: AsyncSession,
    team: Team,
    post_id: uuid.UUID,
) -> ScheduledPost:
    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_id,
            ScheduledPost.team_id == team.id,
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled post not found",
        )
    return post


async def _verify_connection(
    db: AsyncSession,
    team: Team,
    connection_id: uuid.UUID,
) -> PlatformConnection:
    result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.id == connection_id,
            PlatformConnection.team_id == team.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform connection not found",
        )
    return conn


async def _verify_inspired_video(
    db: AsyncSession,
    video_id: uuid.UUID,
) -> None:
    result = await db.execute(select(Video).where(Video.id == video_id))
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="inspired_by_video_id references a video that does not exist",
        )


# ----------------------------------------------------------------------------
# Scheduled post CRUD — public API
# ----------------------------------------------------------------------------


async def create_scheduled_post(
    db: AsyncSession,
    team: Team,
    profile: Profile,
    payload: ScheduledPostCreate,
) -> ScheduledPostResponse:
    """Create a scheduled post.

    Validates that:
    - The connection belongs to the team
    - The connection's platform matches the post's platform
    - The inspired_by_video_id (if provided) exists
    """
    conn = await _verify_connection(db, team, payload.connection_id)

    if conn.platform != payload.platform.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Connection is for {conn.platform!r}, "
                f"not {payload.platform.value!r}"
            ),
        )

    if payload.inspired_by_video_id:
        await _verify_inspired_video(db, payload.inspired_by_video_id)

    post = ScheduledPost(
        team_id=team.id,
        connection_id=payload.connection_id,
        created_by=profile.id,
        inspired_by_video_id=payload.inspired_by_video_id,
        platform=payload.platform.value,
        title=payload.title,
        description=payload.description,
        hashtags=payload.hashtags,
        file_key=payload.file_key,
        scheduled_for=payload.scheduled_for,
        status=_initial_status(payload.scheduled_for).value,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return ScheduledPostResponse.model_validate(post)


async def list_scheduled_posts(
    db: AsyncSession,
    team: Team,
    pagination: PaginationParams,
    status_filter: PostStatus | None = None,
) -> PaginatedResponse[ScheduledPostResponse]:
    """Cursor-paginated list, newest first. Optional status filter."""
    query = select(ScheduledPost).where(ScheduledPost.team_id == team.id)
    if status_filter:
        query = query.where(ScheduledPost.status == status_filter.value)
    return await paginate(
        db=db,
        query=query,
        model=ScheduledPost,
        schema=ScheduledPostResponse,
        params=pagination,
    )


async def get_scheduled_post(
    db: AsyncSession,
    team: Team,
    post_id: uuid.UUID,
) -> ScheduledPostResponse:
    post = await _get_post_or_404(db, team, post_id)
    return ScheduledPostResponse.model_validate(post)


async def update_scheduled_post(
    db: AsyncSession,
    team: Team,
    post_id: uuid.UUID,
    payload: ScheduledPostUpdate,
) -> ScheduledPostResponse:
    """Update a scheduled post.

    Rejects edits to posts in `publishing` or `published` state. Status
    transitions are validated against `ALLOWED_STATUS_TRANSITIONS`.
    """
    post = await _get_post_or_404(db, team, post_id)

    current_status = PostStatus(post.status)
    if current_status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit a post in status '{current_status.value}'",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Status transition: validate then apply, then drop from update_data so it
    # doesn't get setattr'd a second time.
    if "status" in update_data:
        new_status_raw = update_data.pop("status")
        new_status = (
            new_status_raw
            if isinstance(new_status_raw, PostStatus)
            else PostStatus(new_status_raw)
        )
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, frozenset())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot transition from '{current_status.value}' "
                    f"to '{new_status.value}'"
                ),
            )
        post.status = new_status.value

    # Inspired-by reference must point at a real video.
    if update_data.get("inspired_by_video_id"):
        await _verify_inspired_video(db, update_data["inspired_by_video_id"])

    for key, value in update_data.items():
        setattr(post, key, value)

    await db.commit()
    await db.refresh(post)
    return ScheduledPostResponse.model_validate(post)


async def delete_scheduled_post(
    db: AsyncSession,
    team: Team,
    storage: StorageBackend,
    post_id: uuid.UUID,
) -> None:
    """Delete a scheduled post and best-effort delete its file from storage.

    Storage deletion failures are logged but do not fail the request — the
    DB row is the source of truth, and orphaned files can be GC'd separately.
    """
    post = await _get_post_or_404(db, team, post_id)
    file_key = post.file_key

    await db.delete(post)
    await db.commit()

    if file_key:
        try:
            await storage.delete(file_key)
        except Exception as e:
            logger.warning(
                f"Failed to delete file {file_key} for post {post_id}: {e}"
            )
