"""Analytics service — aggregation queries for the dashboard and detail pages."""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Team
from app.creators.models import Creator, CreatorSnapshot, CreatorTracking
from app.discovery.models import Niche, NicheVideo
from app.platforms.base import Platform
from app.videos.models import Video, VideoSnapshot, VideoTracking

from app.analytics.schemas import (
    CreatorTimelinePoint,
    CreatorTimelineResponse,
    NichePerformanceDay,
    NichePerformanceResponse,
    NichePlatformBreakdown,
    OverviewResponse,
    RecentOutlier,
    RecentOutliersResponse,
    VideoTimelinePoint,
    VideoTimelineResponse,
)


async def get_overview(db: AsyncSession, team: Team) -> OverviewResponse:
    """Aggregate counts for the dashboard stat cards."""
    creators = await db.scalar(
        select(func.count()).select_from(CreatorTracking).where(
            CreatorTracking.team_id == team.id
        )
    )
    videos = await db.scalar(
        select(func.count()).select_from(VideoTracking).where(
            VideoTracking.team_id == team.id
        )
    )
    niches = await db.scalar(
        select(func.count()).select_from(Niche).where(
            Niche.team_id == team.id, Niche.is_active.is_(True)
        )
    )

    # Total outliers across all the team's niches
    team_niche_ids = select(Niche.id).where(Niche.team_id == team.id)
    outliers = await db.scalar(
        select(func.count()).select_from(NicheVideo).where(
            NicheVideo.niche_id.in_(team_niche_ids),
            NicheVideo.outlier_score >= 3.0,
        )
    )

    # Snapshots taken in last 24h (indicates worker health)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = await db.scalar(
        select(func.count()).select_from(CreatorSnapshot).where(
            CreatorSnapshot.snapshot_date >= date.today()
        )
    )

    return OverviewResponse(
        tracked_creators=creators or 0,
        tracked_videos=videos or 0,
        active_niches=niches or 0,
        total_outliers=outliers or 0,
        recent_snapshots_24h=recent or 0,
    )


async def get_creator_timeline(
    db: AsyncSession,
    team: Team,
    creator_id: uuid.UUID,
    days: int = 30,
) -> CreatorTimelineResponse:
    """Daily snapshots for a tracked creator, suitable for line charts."""
    # Verify team owns this tracking
    tracking = await db.scalar(
        select(CreatorTracking).where(
            CreatorTracking.team_id == team.id,
            CreatorTracking.creator_id == creator_id,
        )
    )
    if not tracking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Creator not tracked by your team")

    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(CreatorSnapshot)
        .where(
            CreatorSnapshot.creator_id == creator_id,
            CreatorSnapshot.snapshot_date >= since,
        )
        .order_by(CreatorSnapshot.snapshot_date.asc())
    )
    snapshots = result.scalars().all()

    return CreatorTimelineResponse(
        creator_id=creator_id,
        days=days,
        points=[CreatorTimelinePoint.model_validate(s) for s in snapshots],
    )


async def get_video_timeline(
    db: AsyncSession,
    team: Team,
    video_id: uuid.UUID,
    hours: int = 72,
) -> VideoTimelineResponse:
    """Video snapshots for velocity curves."""
    tracking = await db.scalar(
        select(VideoTracking).where(
            VideoTracking.team_id == team.id,
            VideoTracking.video_id == video_id,
        )
    )
    if not tracking:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not tracked by your team")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(VideoSnapshot)
        .where(
            VideoSnapshot.video_id == video_id,
            VideoSnapshot.snapshot_at >= since,
        )
        .order_by(VideoSnapshot.snapshot_at.asc())
    )
    snapshots = result.scalars().all()

    return VideoTimelineResponse(
        video_id=video_id,
        hours=hours,
        points=[VideoTimelinePoint.model_validate(s) for s in snapshots],
    )


async def get_niche_performance(
    db: AsyncSession,
    team: Team,
    niche_id: uuid.UUID,
    days: int = 30,
) -> NichePerformanceResponse:
    """Niche-level analytics: platform breakdown + daily discovery trend."""
    niche = await db.scalar(
        select(Niche).where(Niche.id == niche_id, Niche.team_id == team.id)
    )
    if not niche:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Niche not found")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Platform breakdown
    platform_rows = await db.execute(
        select(Video.platform, func.count())
        .join(NicheVideo, NicheVideo.video_id == Video.id)
        .where(NicheVideo.niche_id == niche_id)
        .group_by(Video.platform)
    )
    platform_breakdown = [
        NichePlatformBreakdown(platform=row[0], count=row[1])
        for row in platform_rows
    ]

    # Total counts
    total_videos = sum(pb.count for pb in platform_breakdown)

    total_outliers = await db.scalar(
        select(func.count()).select_from(NicheVideo).where(
            NicheVideo.niche_id == niche_id,
            NicheVideo.outlier_score >= 3.0,
        )
    ) or 0

    # Daily discovery trend
    daily_rows = await db.execute(
        select(
            cast(NicheVideo.discovered_at, Date).label("day"),
            func.count().label("videos_discovered"),
            func.count().filter(NicheVideo.outlier_score >= 3.0).label("outliers"),
        )
        .where(
            NicheVideo.niche_id == niche_id,
            NicheVideo.discovered_at >= since,
        )
        .group_by("day")
        .order_by("day")
    )
    daily = [
        NichePerformanceDay(day=row.day, videos_discovered=row.videos_discovered, outliers=row.outliers)
        for row in daily_rows
    ]

    return NichePerformanceResponse(
        niche_id=niche_id,
        days=days,
        total_videos=total_videos,
        total_outliers=total_outliers,
        platform_breakdown=platform_breakdown,
        daily=daily,
    )


async def get_recent_outliers(
    db: AsyncSession,
    team: Team,
    limit: int = 10,
) -> RecentOutliersResponse:
    """Top recent outliers across all the team's niches."""
    team_niche_ids = select(Niche.id).where(Niche.team_id == team.id)

    result = await db.execute(
        select(
            NicheVideo.id.label("niche_video_id"),
            NicheVideo.niche_id,
            Niche.name.label("niche_name"),
            NicheVideo.outlier_score,
            NicheVideo.discovered_at,
            Video.id.label("video_id"),
            Video.platform,
            Video.title,
            Video.thumbnail_url,
            Video.latest_views.label("views"),
            Video.latest_likes.label("likes"),
            Video.latest_engagement_rate.label("engagement_rate"),
        )
        .join(Video, NicheVideo.video_id == Video.id)
        .join(Niche, NicheVideo.niche_id == Niche.id)
        .where(
            NicheVideo.niche_id.in_(team_niche_ids),
            NicheVideo.outlier_score >= 3.0,
        )
        .order_by(desc(NicheVideo.discovered_at))
        .limit(limit)
    )

    items = [
        RecentOutlier(
            niche_video_id=row.niche_video_id,
            niche_id=row.niche_id,
            niche_name=row.niche_name,
            outlier_score=row.outlier_score,
            discovered_at=row.discovered_at,
            video_id=row.video_id,
            platform=Platform(row.platform),
            title=row.title,
            thumbnail_url=row.thumbnail_url,
            views=row.views,
            likes=row.likes,
            engagement_rate=row.engagement_rate,
        )
        for row in result
    ]

    return RecentOutliersResponse(items=items, total=len(items))
