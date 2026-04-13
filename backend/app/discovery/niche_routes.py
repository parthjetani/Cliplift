"""Niche routes — CRUD + feed."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_team
from app.auth.models import Team
from app.billing.enforcement import require_active_plan
from app.common.pagination import PaginatedResponse
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params
from app.discovery.niche_schemas import (
    NicheCreate,
    NicheFeedItem,
    NicheResponse,
    NicheUpdate,
)
from app.discovery.niche_service import (
    create_niche,
    delete_niche,
    get_niche,
    get_niche_feed,
    list_niches,
    update_niche,
)

router = APIRouter(prefix="/niches", tags=["niches"])


@router.get(
    "",
    response_model=PaginatedResponse[NicheResponse],
    summary="List the team's niches",
)
async def list_niches_endpoint(
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> PaginatedResponse[NicheResponse]:
    return await list_niches(db, team, pagination)


@router.post(
    "",
    response_model=NicheResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new niche",
)
async def create_niche_endpoint(
    body: NicheCreate,
    team: Annotated[Team, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NicheResponse:
    return await create_niche(db, team, body)


@router.get(
    "/{niche_id}",
    response_model=NicheResponse,
    summary="Get a single niche",
)
async def get_niche_endpoint(
    niche_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NicheResponse:
    return await get_niche(db, team, niche_id)


@router.put(
    "/{niche_id}",
    response_model=NicheResponse,
    summary="Update a niche",
)
async def update_niche_endpoint(
    niche_id: uuid.UUID,
    body: NicheUpdate,
    team: Annotated[Team, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NicheResponse:
    return await update_niche(db, team, niche_id, body)


@router.delete(
    "/{niche_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a niche",
)
async def delete_niche_endpoint(
    niche_id: uuid.UUID,
    team: Annotated[Team, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await delete_niche(db, team, niche_id)


@router.get(
    "/{niche_id}/feed",
    response_model=PaginatedResponse[NicheFeedItem],
    summary="Get auto-discovered videos for a niche",
    description=(
        "Returns videos discovered by the auto-discovery worker for this niche, "
        "sorted by discovered_at (newest first). Empty until the worker has run."
    ),
)
async def get_niche_feed_endpoint(
    niche_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> PaginatedResponse[NicheFeedItem]:
    return await get_niche_feed(db, team, niche_id, pagination)
