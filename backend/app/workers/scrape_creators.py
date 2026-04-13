"""Daily worker: refresh metrics for all tracked creators.

Triggered by QStash on a daily schedule (in production) or manually via:

    curl -X POST http://localhost:8000/api/v1/workers/scrape-creators \
         -H "X-Dev-Worker-Token: <ENCRYPTION_KEY>"

For each Creator with last_scraped_at NULL or > 24h old:
- Fetch fresh data via DataProviderRouter.get_creator()
- Upsert today's CreatorSnapshot row
- Update creator.last_scraped_at
"""

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.creators.models import Creator, CreatorSnapshot
from app.platforms.base import Platform
from app.platforms.router import DataProviderRouter

logger = logging.getLogger(__name__)


async def scrape_creators(
    db: AsyncSession,
    router: DataProviderRouter,
    max_age_hours: int = 24,
    limit: int = 1000,
) -> dict:
    """Refresh creators that haven't been scraped recently.

    Returns:
        {processed: int, errors: int, skipped: int}
    """
    base_query = select(Creator).where(Creator.is_active.is_(True))

    if max_age_hours > 0:
        # Production / cron mode: only refresh stale creators
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        base_query = base_query.where(
            or_(
                Creator.last_scraped_at.is_(None),
                Creator.last_scraped_at < cutoff,
            )
        )
    # max_age_hours == 0 → force-process every active creator (manual/dev mode)

    result = await db.execute(base_query.limit(limit))
    creators = list(result.scalars().all())

    processed = 0
    errors = 0
    today = date.today()

    for creator in creators:
        try:
            platform = Platform(creator.platform)
            profile = await router.get_creator(platform, creator.platform_id)
            if not profile:
                logger.warning(
                    f"Provider returned None for {creator.platform}:{creator.platform_id}"
                )
                errors += 1
                continue

            # Upsert today's snapshot (idempotent — same creator + same date)
            existing = await db.execute(
                select(CreatorSnapshot).where(
                    CreatorSnapshot.creator_id == creator.id,
                    CreatorSnapshot.snapshot_date == today,
                )
            )
            snapshot = existing.scalar_one_or_none()
            if snapshot:
                snapshot.followers = profile.followers
                snapshot.total_videos = profile.total_videos
            else:
                snapshot = CreatorSnapshot(
                    creator_id=creator.id,
                    followers=profile.followers,
                    total_videos=profile.total_videos,
                    snapshot_date=today,
                )
                db.add(snapshot)

            # Update creator's denormalized fields
            if profile.username:
                creator.username = profile.username
            if profile.display_name:
                creator.display_name = profile.display_name
            if profile.avatar_url:
                creator.avatar_url = profile.avatar_url
            if profile.bio:
                creator.bio = profile.bio
            creator.last_scraped_at = datetime.now(timezone.utc)

            await db.commit()
            processed += 1
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to scrape creator {creator.id}: {e}")
            errors += 1

    return {"processed": processed, "errors": errors, "total": len(creators)}
