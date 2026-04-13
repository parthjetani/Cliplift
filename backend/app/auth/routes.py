"""Auth routes — profile read/update.

Note: there are no register/login/logout endpoints — the frontend calls
Supabase Auth SDK directly. Our backend only validates the JWT and manages
the application-level Profile row.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_profile, get_current_team
from app.auth.models import Profile, Team
from app.auth.schemas import ProfileResponse, ProfileUpdate, TeamResponse
from app.auth.service import update_profile
from app.database import get_db

router = APIRouter(tags=["auth"])


@router.get("/profile", response_model=ProfileResponse)
async def get_my_profile(
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> ProfileResponse:
    """Get the current user's profile."""
    return ProfileResponse.model_validate(profile)


@router.put("/profile", response_model=ProfileResponse)
async def update_my_profile(
    updates: ProfileUpdate,
    profile: Annotated[Profile, Depends(get_current_profile)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Update the current user's profile (name, avatar_url)."""
    updated = await update_profile(db, profile, updates)
    return ProfileResponse.model_validate(updated)


@router.get("/teams/me", response_model=TeamResponse)
async def get_my_team(
    team: Annotated[Team, Depends(get_current_team)],
) -> TeamResponse:
    """Get the current user's team with plan + trial info."""
    return TeamResponse.model_validate(team)
