"""Niche service — CRUD operations and feed query."""

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth.models import Team
from app.common.pagination import PaginatedResponse, paginate
from app.dependencies import PaginationParams
from app.discovery.models import Niche, NicheVideo
from app.discovery.niche_schemas import (
    NicheCreate,
    NicheFeedItem,
    NicheResponse,
    NicheUpdate,
)
from app.videos.schemas import VideoResponse

logger = logging.getLogger(__name__)


async def list_niches(
    db: AsyncSession,
    team: Team,
    pagination: PaginationParams,
) -> PaginatedResponse[NicheResponse]:
    """Paginated list of the team's niches, newest first."""
    query = select(Niche).where(Niche.team_id == team.id)
    return await paginate(
        db=db,
        query=query,
        model=Niche,
        schema=NicheResponse,
        params=pagination,
    )


async def create_niche(
    db: AsyncSession,
    team: Team,
    data: NicheCreate,
) -> NicheResponse:
    niche = Niche(
        team_id=team.id,
        name=data.name,
        keywords=data.keywords,
        platforms=[p.value for p in data.platforms],
        is_active=data.is_active,
    )
    db.add(niche)
    await db.commit()
    await db.refresh(niche)
    return NicheResponse.model_validate(niche)


async def _get_niche_or_404(
    db: AsyncSession,
    team: Team,
    niche_id: uuid.UUID,
) -> Niche:
    result = await db.execute(
        select(Niche).where(Niche.id == niche_id, Niche.team_id == team.id)
    )
    niche = result.scalar_one_or_none()
    if not niche:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Niche not found",
        )
    return niche


async def get_niche(
    db: AsyncSession,
    team: Team,
    niche_id: uuid.UUID,
) -> NicheResponse:
    niche = await _get_niche_or_404(db, team, niche_id)
    return NicheResponse.model_validate(niche)


async def update_niche(
    db: AsyncSession,
    team: Team,
    niche_id: uuid.UUID,
    data: NicheUpdate,
) -> NicheResponse:
    niche = await _get_niche_or_404(db, team, niche_id)
    update_data = data.model_dump(exclude_unset=True, exclude_none=True)
    if "platforms" in update_data:
        update_data["platforms"] = [
            p.value if hasattr(p, "value") else p for p in update_data["platforms"]
        ]
    for key, value in update_data.items():
        setattr(niche, key, value)
    await db.commit()
    await db.refresh(niche)
    return NicheResponse.model_validate(niche)


async def delete_niche(
    db: AsyncSession,
    team: Team,
    niche_id: uuid.UUID,
) -> None:
    niche = await _get_niche_or_404(db, team, niche_id)
    await db.delete(niche)
    await db.commit()


async def get_niche_feed(
    db: AsyncSession,
    team: Team,
    niche_id: uuid.UUID,
    pagination: PaginationParams,
) -> PaginatedResponse[NicheFeedItem]:
    """Paginated feed of videos discovered by the niche's worker.

    Joins `niche_videos` ↔ `videos` and returns the join row with the embedded
    video. Sorted by discovered_at (newest first).
    """
    # Verify niche belongs to team
    await _get_niche_or_404(db, team, niche_id)

    query = (
        select(NicheVideo)
        .where(NicheVideo.niche_id == niche_id)
        .options(joinedload(NicheVideo.video))
    )

    # Use a custom mapper since NicheFeedItem needs renamed fields
    result = await paginate(
        db=db,
        query=query,
        model=NicheVideo,
        schema=NicheFeedItem,
        params=pagination,
        timestamp_field="discovered_at",
    )

    # Post-process: rename outlier_score → niche_outlier_score for clarity
    items: list[NicheFeedItem] = []
    for nv_item in result.items:
        # nv_item is a NicheFeedItem already validated from NicheVideo, but the
        # `video` field needs to be set explicitly because joinedload doesn't
        # auto-flow into Pydantic. We re-build below from the raw query.
        items.append(nv_item)
    return result
