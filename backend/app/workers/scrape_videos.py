"""6-hourly worker: refresh metrics for tracked videos + compute view velocity.

For each Video that has been tracked by any team:
- Fetch fresh metrics via DataProviderRouter.get_video_metrics()
- Insert a new VideoSnapshot
- Compute view_velocity from the previous snapshot
- Update Video.latest_* denormalized columns
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platforms.base import Platform
from app.platforms.router import DataProviderRouter
from app.videos.models import Video, VideoSnapshot, VideoTracking

logger = logging.getLogger(__name__)


async def scrape_videos(
    db: AsyncSession,
    router: DataProviderRouter,
    max_age_hours: int = 6,
    limit: int = 1000,
) -> dict:
    """Refresh tracked videos that haven't been scraped recently."""
    # Only scrape videos that are actively tracked by at least one team
    tracked_subquery = exists().where(VideoTracking.video_id == Video.id)
    base_query = select(Video).where(tracked_subquery)

    if max_age_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        base_query = base_query.where(
            or_(
                Video.last_scraped_at.is_(None),
                Video.last_scraped_at < cutoff,
            )
        )

    result = await db.execute(base_query.limit(limit))
    videos = list(result.scalars().all())

    processed = 0
    errors = 0
    now = datetime.now(timezone.utc)

    for video in videos:
        try:
            platform = Platform(video.platform)
            metrics = await router.get_video_metrics(platform, video.platform_video_id)
            if not metrics:
                errors += 1
                continue

            # Compute view velocity from the previous snapshot
            previous_result = await db.execute(
                select(VideoSnapshot)
                .where(VideoSnapshot.video_id == video.id)
                .order_by(desc(VideoSnapshot.snapshot_at))
                .limit(1)
            )
            previous = previous_result.scalar_one_or_none()

            view_velocity = None
            if previous and previous.views is not None and metrics.views >= previous.views:
                hours_elapsed = (
                    metrics.fetched_at - previous.snapshot_at
                ).total_seconds() / 3600.0
                if hours_elapsed > 0:
                    view_velocity = (metrics.views - previous.views) / hours_elapsed

            # Insert new snapshot
            snapshot = VideoSnapshot(
                video_id=video.id,
                views=metrics.views,
                likes=metrics.likes,
                comments=metrics.comments,
                shares=metrics.shares,
                engagement_rate=metrics.engagement_rate,
                view_velocity=view_velocity,
                snapshot_at=metrics.fetched_at,
            )
            db.add(snapshot)

            # Update denormalized columns on Video
            video.latest_views = metrics.views
            video.latest_likes = metrics.likes
            video.latest_comments = metrics.comments
            video.latest_shares = metrics.shares
            video.latest_engagement_rate = metrics.engagement_rate
            video.latest_snapshot_at = metrics.fetched_at
            video.last_scraped_at = now

            await db.commit()
            processed += 1
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to scrape video {video.id}: {e}")
            errors += 1

    return {"processed": processed, "errors": errors, "total": len(videos)}
