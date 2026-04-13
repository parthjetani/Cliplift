"""Daily worker: collect performance metrics for published posts.

For each ScheduledPost with status='published' and a `platform_post_id`,
fetches current metrics via the DataProviderRouter and inserts a
PostAnalytics snapshot. This closes the "measure the results" loop —
without it, users would have to check YouTube/Instagram manually to see
how their Cliplift-published posts performed.

Schedule: daily via QStash cron.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platforms.base import Platform
from app.platforms.router import DataProviderRouter
from app.publishing.models import PostAnalytics, ScheduledPost

logger = logging.getLogger(__name__)


async def collect_analytics(
    db: AsyncSession,
    router: DataProviderRouter,
    max_age_hours: int = 24,
    limit: int = 500,
) -> dict:
    """Fetch metrics for published posts that haven't been scraped recently.

    Only processes posts with `status='published'` and a `platform_post_id`
    (i.e., posts that were actually pushed to a platform). Posts without a
    platform_post_id are mock-published or failed — nothing to scrape.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    # Find published posts whose latest analytics snapshot is stale (or missing)
    # We check by joining to PostAnalytics and looking for max(snapshot_at) < cutoff.
    # Simpler approach: just re-scrape all published posts and let the daily cadence
    # handle dedup (one snapshot per day is fine at this scale).
    query = (
        select(ScheduledPost)
        .where(
            ScheduledPost.status == "published",
            ScheduledPost.platform_post_id.is_not(None),
        )
        .order_by(ScheduledPost.published_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    posts = list(result.scalars().all())

    processed = 0
    errors = 0

    for post in posts:
        try:
            platform = Platform(post.platform)
            metrics = await router.get_video_metrics(
                platform, post.platform_post_id
            )
            if not metrics:
                # Provider returned nothing (e.g., mock provider for a mock post_id)
                # Skip silently — this is expected for mock-published posts
                continue

            snapshot = PostAnalytics(
                post_id=post.id,
                views=metrics.views,
                likes=metrics.likes,
                comments=metrics.comments,
                shares=metrics.shares,
                snapshot_at=metrics.fetched_at,
            )
            db.add(snapshot)
            await db.commit()
            processed += 1

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to collect analytics for post {post.id}: {e}")
            errors += 1

    return {"processed": processed, "errors": errors, "total": len(posts)}
