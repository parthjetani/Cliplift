"""Auth service — profile lookups, idempotent creation, default team management."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Profile, Team
from app.auth.schemas import ProfileUpdate

logger = logging.getLogger(__name__)


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> Profile | None:
    """Fetch a profile by ID. Returns None if not found."""
    result = await db.execute(select(Profile).where(Profile.id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    email: str,
) -> Profile:
    """Idempotent profile lookup/creation.

    The Supabase trigger `on_auth_user_created` should auto-create the profile
    on signup, but this function handles two edge cases:
    1. Race condition: API call arrives before the trigger has fired
    2. Existing user from before the trigger was deployed

    Always returns a valid profile.
    """
    profile = await get_profile(db, user_id)
    if profile:
        return profile

    # Trigger hasn't fired yet — create the profile ourselves
    logger.info(f"Profile not found for user {user_id}, creating now")
    profile = Profile(id=user_id, email=email)
    db.add(profile)
    try:
        await db.commit()
        await db.refresh(profile)
    except Exception:
        # Trigger may have fired during our INSERT — fetch again
        await db.rollback()
        profile = await get_profile(db, user_id)
        if not profile:
            raise

    return profile


async def update_profile(
    db: AsyncSession,
    profile: Profile,
    updates: ProfileUpdate,
) -> Profile:
    """Apply user-supplied updates to a profile."""
    update_data = updates.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile


# ----------------------------------------------------------------------------
# Default team management
# ----------------------------------------------------------------------------
#
# Every user gets exactly one auto-created "Personal" team on first API call.
# This is the Linear/Notion pattern — no team-creation friction at signup, but
# all per-team data (creators, niches, posts) has a stable owner from day one.
#
# Team-switching UI (multi-team workspaces) is a Phase 2 feature.


async def get_default_team(db: AsyncSession, profile: Profile) -> Team | None:
    """Fetch the user's first owned team. Returns None if no team exists yet."""
    result = await db.execute(
        select(Team)
        .where(Team.owner_id == profile.id)
        .order_by(Team.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_or_create_default_team(
    db: AsyncSession,
    profile: Profile,
) -> Team:
    """Idempotent: returns the user's default team, creating one if needed.

    Called from `get_current_team` dependency, so it runs on every protected
    request. Must be cheap when the team already exists (single SELECT).
    """
    team = await get_default_team(db, profile)
    if team:
        return team

    logger.info(f"Creating default 'Personal' team for user {profile.id}")
    team = Team(
        name="Personal",
        owner_id=profile.id,
        plan="creator",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
        max_tracked_creators=3,
        max_seats=1,
    )
    db.add(team)
    try:
        await db.commit()
        await db.refresh(team)
    except Exception:
        # Concurrent request may have created the team — fetch and return
        await db.rollback()
        team = await get_default_team(db, profile)
        if not team:
            raise

    return team
