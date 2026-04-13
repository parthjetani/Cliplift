"""Hourly worker: run niche keyword searches and populate niche_videos.

For each active Niche:
- Build a query from the niche's keywords (joined with spaces)
- Search across the niche's configured platforms via DataProviderRouter
- Apply Z-score outlier detection per platform
- Upsert Video rows for new results
- Insert NicheVideo rows linking videos to the niche with niche-relative scores
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.models import Niche, NicheVideo
from app.discovery.outlier import calculate_outlier_scores
from app.platforms.base import Platform, VideoSearchResult
from app.platforms.router import DataProviderRouter
from app.videos.models import Video

logger = logging.getLogger(__name__)


async def _upsert_video(
    db: AsyncSession, result: VideoSearchResult
) -> Video:
    """Find or create a Video row from a search result."""
    existing = await db.execute(
        select(Video).where(
            Video.platform == result.platform.value,
            Video.platform_video_id == result.platform_video_id,
        )
    )
    video = existing.scalar_one_or_none()
    if video:
        # Update denormalized metrics on revisit
        video.latest_views = result.views
        video.latest_likes = result.likes
        video.latest_comments = result.comments
        video.latest_shares = result.shares
        video.latest_engagement_rate = result.engagement_rate
        video.latest_snapshot_at = datetime.now(timezone.utc)
        return video

    video = Video(
        platform=result.platform.value,
        platform_video_id=result.platform_video_id,
        title=result.title,
        description=result.description,
        thumbnail_url=result.thumbnail_url,
        duration_seconds=result.duration_seconds,
        published_at=result.published_at,
        hashtags=result.hashtags or None,
        is_short=True,
        latest_views=result.views,
        latest_likes=result.likes,
        latest_comments=result.comments,
        latest_shares=result.shares,
        latest_engagement_rate=result.engagement_rate,
        latest_snapshot_at=datetime.now(timezone.utc),
        last_scraped_at=datetime.now(timezone.utc),
    )
    db.add(video)
    await db.flush()
    return video


async def discover_trends(
    db: AsyncSession,
    router: DataProviderRouter,
    max_age_hours: int = 1,
    limit_per_platform: int = 20,
    niche_limit: int = 100,
) -> dict:
    """Run discovery for active niches that haven't been analyzed recently.

    Niches are picked in order of staleness so brand-new (`last_analyzed_at IS
    NULL`) niches always run before previously-processed ones, even if there
    are more than `niche_limit` total active niches in the DB. This guarantees
    that a freshly-created niche will be processed by the next worker run.
    """
    base_query = select(Niche).where(Niche.is_active.is_(True))

    if max_age_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        base_query = base_query.where(
            or_(
                Niche.last_analyzed_at.is_(None),
                Niche.last_analyzed_at < cutoff,
            )
        )

    # NULLS FIRST so unprocessed niches always lead; tiebreak on created_at
    # so the oldest stale niche runs before newer ones (FIFO).
    base_query = base_query.order_by(
        Niche.last_analyzed_at.asc().nulls_first(),
        Niche.created_at.asc(),
    )

    result = await db.execute(base_query.limit(niche_limit))
    niches = list(result.scalars().all())

    processed = 0
    errors = 0
    total_videos_added = 0

    for niche in niches:
        try:
            query = " ".join(niche.keywords)
            platforms = [Platform(p) for p in niche.platforms]

            by_platform = await router.search_videos(
                query=query,
                platforms=platforms,
                limit_per_platform=limit_per_platform,
            )

            for platform, results in by_platform.items():
                # Apply niche-relative outlier scoring (per platform)
                scored = calculate_outlier_scores(results)

                for video_result in scored:
                    video = await _upsert_video(db, video_result)

                    # Idempotent: only insert NicheVideo if not already linked
                    existing = await db.execute(
                        select(NicheVideo).where(
                            NicheVideo.niche_id == niche.id,
                            NicheVideo.video_id == video.id,
                        )
                    )
                    if existing.scalar_one_or_none() is None:
                        nv = NicheVideo(
                            niche_id=niche.id,
                            video_id=video.id,
                            outlier_score=video_result.outlier_score,
                        )
                        db.add(nv)
                        total_videos_added += 1

            niche.last_analyzed_at = datetime.now(timezone.utc)
            await db.commit()
            processed += 1
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to analyze niche {niche.id}: {e}")
            errors += 1

    return {
        "processed": processed,
        "errors": errors,
        "total_niches": len(niches),
        "videos_added": total_videos_added,
    }
