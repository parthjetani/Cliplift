"""Videos service — track, untrack, list, fetch."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth.models import Team
from app.common.pagination import PaginatedResponse, paginate
from app.dependencies import PaginationParams
from app.platforms.base import Platform
from app.platforms.router import DataProviderRouter
from app.videos.models import Video, VideoSnapshot, VideoTracking
from app.videos.schemas import (
    TrackedVideoResponse,
    VideoDetailResponse,
    VideoResponse,
    VideoSnapshotResponse,
)

logger = logging.getLogger(__name__)


async def list_tracked_videos(
    db: AsyncSession,
    team: Team,
    pagination: PaginationParams,
) -> PaginatedResponse[TrackedVideoResponse]:
    query = (
        select(VideoTracking)
        .where(VideoTracking.team_id == team.id)
        .options(joinedload(VideoTracking.video))
    )
    return await paginate(
        db=db,
        query=query,
        model=VideoTracking,
        schema=TrackedVideoResponse,
        params=pagination,
        timestamp_field="tracked_at",
    )


async def _get_or_create_video(
    db: AsyncSession,
    platform: Platform,
    platform_video_id: str,
    router: DataProviderRouter,
) -> Video:
    """Find or fetch a Video. Uses get_video_metrics + minimal upsert."""
    result = await db.execute(
        select(Video).where(
            Video.platform == platform.value,
            Video.platform_video_id == platform_video_id,
        )
    )
    video = result.scalar_one_or_none()
    if video:
        return video

    metrics = await router.get_video_metrics(platform, platform_video_id)
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video {platform_video_id} not found on {platform.value}",
        )

    now = datetime.now(timezone.utc)
    video = Video(
        platform=platform.value,
        platform_video_id=platform_video_id,
        title=None,
        description=None,
        latest_views=metrics.views,
        latest_likes=metrics.likes,
        latest_comments=metrics.comments,
        latest_shares=metrics.shares,
        latest_engagement_rate=metrics.engagement_rate,
        latest_snapshot_at=metrics.fetched_at,
        last_scraped_at=now,
    )
    db.add(video)
    await db.flush()

    # Also create the first VideoSnapshot row so view_velocity can be computed later
    snapshot = VideoSnapshot(
        video_id=video.id,
        views=metrics.views,
        likes=metrics.likes,
        comments=metrics.comments,
        shares=metrics.shares,
        engagement_rate=metrics.engagement_rate,
        snapshot_at=metrics.fetched_at,
    )
    db.add(snapshot)
    await db.flush()

    return video


async def track_video(
    db: AsyncSession,
    team: Team,
    platform: Platform,
    platform_video_id: str,
    router: DataProviderRouter,
) -> TrackedVideoResponse:
    """Track a video for a team. Idempotent."""
    video = await _get_or_create_video(db, platform, platform_video_id, router)

    existing = await db.execute(
        select(VideoTracking).where(
            VideoTracking.team_id == team.id,
            VideoTracking.video_id == video.id,
        )
    )
    tracking = existing.scalar_one_or_none()
    if not tracking:
        tracking = VideoTracking(team_id=team.id, video_id=video.id)
        db.add(tracking)
        await db.commit()
        await db.refresh(tracking)

    return TrackedVideoResponse(
        id=tracking.id,
        video=VideoResponse.model_validate(video),
        tracked_at=tracking.tracked_at,
    )


async def untrack_video(
    db: AsyncSession,
    team: Team,
    video_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(VideoTracking).where(
            VideoTracking.team_id == team.id,
            VideoTracking.video_id == video_id,
        )
    )
    tracking = result.scalar_one_or_none()
    if not tracking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video is not tracked by your team",
        )
    await db.delete(tracking)
    await db.commit()


async def get_video_detail(
    db: AsyncSession,
    team: Team,
    video_id: uuid.UUID,
) -> VideoDetailResponse:
    video_result = await db.execute(select(Video).where(Video.id == video_id))
    video = video_result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    tracking_result = await db.execute(
        select(VideoTracking).where(
            VideoTracking.team_id == team.id,
            VideoTracking.video_id == video_id,
        )
    )
    tracking = tracking_result.scalar_one_or_none()

    snapshots_result = await db.execute(
        select(VideoSnapshot)
        .where(VideoSnapshot.video_id == video_id)
        .order_by(desc(VideoSnapshot.snapshot_at))
        .limit(50)
    )
    snapshots = list(snapshots_result.scalars().all())

    return VideoDetailResponse(
        video=VideoResponse.model_validate(video),
        tracking=TrackedVideoResponse(
            id=tracking.id,
            video=VideoResponse.model_validate(video),
            tracked_at=tracking.tracked_at,
        )
        if tracking
        else None,
        recent_snapshots=[
            VideoSnapshotResponse.model_validate(s) for s in snapshots
        ],
    )
