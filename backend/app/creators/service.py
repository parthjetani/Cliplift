"""Creators service — track, untrack, list, fetch."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth.models import Team
from app.common.pagination import PaginatedResponse, paginate
from app.creators.models import Creator, CreatorSnapshot, CreatorTracking
from app.creators.schemas import (
    CreatorDetailResponse,
    CreatorResponse,
    CreatorSnapshotResponse,
    TrackedCreatorResponse,
)
from app.dependencies import PaginationParams
from app.platforms.base import Platform
from app.platforms.router import DataProviderRouter

logger = logging.getLogger(__name__)


async def list_tracked_creators(
    db: AsyncSession,
    team: Team,
    pagination: PaginationParams,
) -> PaginatedResponse[TrackedCreatorResponse]:
    """List the team's tracked creators (paginated)."""
    query = (
        select(CreatorTracking)
        .where(CreatorTracking.team_id == team.id)
        .options(joinedload(CreatorTracking.creator))
    )
    return await paginate(
        db=db,
        query=query,
        model=CreatorTracking,
        schema=TrackedCreatorResponse,
        params=pagination,
        timestamp_field="tracked_at",
    )


async def count_tracked_creators(db: AsyncSession, team: Team) -> int:
    result = await db.execute(
        select(func.count()).select_from(CreatorTracking).where(
            CreatorTracking.team_id == team.id
        )
    )
    return result.scalar_one()


async def _get_or_create_creator(
    db: AsyncSession,
    platform: Platform,
    platform_id: str,
    router: DataProviderRouter,
) -> Creator:
    """Find an existing Creator row or fetch from the provider and insert."""
    result = await db.execute(
        select(Creator).where(
            Creator.platform == platform.value,
            Creator.platform_id == platform_id,
        )
    )
    creator = result.scalar_one_or_none()
    if creator:
        return creator

    # Fetch from data provider
    profile = await router.get_creator(platform, platform_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Creator {platform_id} not found on {platform.value}",
        )

    creator = Creator(
        platform=platform.value,
        platform_id=profile.platform_id,
        username=profile.username,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        is_active=True,
        last_scraped_at=datetime.now(timezone.utc),
    )
    db.add(creator)
    await db.flush()  # populate creator.id without committing yet
    return creator


async def track_creator(
    db: AsyncSession,
    team: Team,
    platform: Platform,
    platform_id: str,
    router: DataProviderRouter,
    notes: str | None = None,
) -> TrackedCreatorResponse:
    """Track a creator for a team. Idempotent: returns the existing tracking row if already tracked.

    Note: plan-limit checks are handled by the route layer via
    `require_active_plan` + `enforce_creator_tracking_limit` dependencies
    (see billing/enforcement.py). This service function just does the DB work.
    """
    # Find or fetch the creator
    creator = await _get_or_create_creator(db, platform, platform_id, router)

    # Check if already tracked
    existing = await db.execute(
        select(CreatorTracking).where(
            CreatorTracking.team_id == team.id,
            CreatorTracking.creator_id == creator.id,
        )
    )
    tracking = existing.scalar_one_or_none()
    if tracking:
        # Idempotent — refresh notes if provided
        if notes is not None:
            tracking.notes = notes
            await db.commit()
            await db.refresh(tracking)
    else:
        tracking = CreatorTracking(
            team_id=team.id,
            creator_id=creator.id,
            notes=notes,
        )
        db.add(tracking)
        await db.commit()
        await db.refresh(tracking)

    # Build response with creator eager-loaded
    return TrackedCreatorResponse(
        id=tracking.id,
        creator=CreatorResponse.model_validate(creator),
        tracked_at=tracking.tracked_at,
        notes=tracking.notes,
        latest_followers=None,  # populated by snapshot worker
    )


async def untrack_creator(
    db: AsyncSession,
    team: Team,
    creator_id: uuid.UUID,
) -> None:
    """Remove a tracking row. Raises 404 if not tracked."""
    result = await db.execute(
        select(CreatorTracking).where(
            CreatorTracking.team_id == team.id,
            CreatorTracking.creator_id == creator_id,
        )
    )
    tracking = result.scalar_one_or_none()
    if not tracking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator is not tracked by your team",
        )
    await db.delete(tracking)
    await db.commit()


async def get_creator_detail(
    db: AsyncSession,
    team: Team,
    creator_id: uuid.UUID,
) -> CreatorDetailResponse:
    """Fetch creator + tracking + recent snapshots."""
    # Creator
    creator_result = await db.execute(select(Creator).where(Creator.id == creator_id))
    creator = creator_result.scalar_one_or_none()
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found",
        )

    # Tracking row (may be None — creator can exist globally without this team tracking)
    tracking_result = await db.execute(
        select(CreatorTracking).where(
            CreatorTracking.team_id == team.id,
            CreatorTracking.creator_id == creator_id,
        )
    )
    tracking = tracking_result.scalar_one_or_none()

    # Recent snapshots (last 30)
    snapshots_result = await db.execute(
        select(CreatorSnapshot)
        .where(CreatorSnapshot.creator_id == creator_id)
        .order_by(desc(CreatorSnapshot.snapshot_date))
        .limit(30)
    )
    snapshots = list(snapshots_result.scalars().all())

    return CreatorDetailResponse(
        creator=CreatorResponse.model_validate(creator),
        tracking=TrackedCreatorResponse(
            id=tracking.id,
            creator=CreatorResponse.model_validate(creator),
            tracked_at=tracking.tracked_at,
            notes=tracking.notes,
            latest_followers=None,
        )
        if tracking
        else None,
        recent_snapshots=[
            CreatorSnapshotResponse.model_validate(s) for s in snapshots
        ],
    )
