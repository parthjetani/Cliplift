"""FastAPI dependencies for auth: extract user, fetch profile, resolve team.

Usage in route handlers:

    @router.get("/me")
    async def me(
        profile: Profile = Depends(get_current_profile),
        team: Team = Depends(get_current_team),
    ):
        ...
"""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import decode_supabase_jwt, extract_bearer_token
from app.auth.models import Profile, Team
from app.auth.schemas import SupabaseUser
from app.auth.service import get_or_create_default_team, get_or_create_profile
from app.database import get_db


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> SupabaseUser:
    """Extract and validate the Supabase JWT from the Authorization header.

    Returns the decoded user (id + email + role). Does NOT touch the DB —
    use `get_current_profile` if you need the full Profile row.
    """
    token = extract_bearer_token(authorization)
    return decode_supabase_jwt(token)


async def get_current_profile(
    user: Annotated[SupabaseUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Profile:
    """Get the full Profile row for the authenticated user.

    Idempotent — creates the profile if it doesn't exist (handles trigger race).
    """
    return await get_or_create_profile(db, user.id, user.email)


async def get_current_team(
    profile: Annotated[Profile, Depends(get_current_profile)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Team:
    """Get the user's default team for per-team scoped operations.

    Auto-creates a "Personal" team on first call. Used by all endpoints that
    operate on team-scoped data (creators, videos, niches, posts, connections).
    """
    return await get_or_create_default_team(db, profile)
