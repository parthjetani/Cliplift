"""Creators routes — track, untrack, list, detail."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_team
from app.auth.models import Team
from app.billing.enforcement import enforce_creator_tracking_limit, require_active_plan
from app.common.pagination import PaginatedResponse
from app.common.ratelimit import rate_limit
from app.creators.schemas import (
    CreatorDetailResponse,
    TrackCreatorRequest,
    TrackedCreatorResponse,
)
from app.creators.service import (
    get_creator_detail,
    list_tracked_creators,
    track_creator,
    untrack_creator,
)
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params
from app.platforms.router import DataProviderRouter

router = APIRouter(prefix="/creators", tags=["creators"])


def get_router_from_app(request: Request) -> DataProviderRouter:
    """Pull the DataProviderRouter from app.state."""
    return request.app.state.data_provider_router


@router.get(
    "",
    response_model=PaginatedResponse[TrackedCreatorResponse],
    summary="List tracked creators",
)
async def list_creators(
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> PaginatedResponse[TrackedCreatorResponse]:
    return await list_tracked_creators(db, team, pagination)


@router.post(
    "/track",
    response_model=TrackedCreatorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Track a new creator",
    description=(
        "Adds a creator to the team's tracking list. Provide either explicit "
        "(platform + platform_id) or a recognizable URL. "
        "Returns 402 if the team's plan limit is reached."
    ),
    dependencies=[Depends(rate_limit("track_creator", max_requests=20, window_seconds=60))],
)
async def track_creator_endpoint(
    body: TrackCreatorRequest,
    team: Annotated[Team, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_db)],
    router: Annotated[DataProviderRouter, Depends(get_router_from_app)],
) -> TrackedCreatorResponse:
    await enforce_creator_tracking_limit(db, team)
    try:
        platform, platform_id = body.resolve()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    return await track_creator(
        db=db,
        team=team,
        platform=platform,
        platform_id=platform_id,
        router=router,
        notes=body.notes,
    )


@router.delete(
    "/{creator_id}/untrack",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Untrack a creator",
)
async def untrack_creator_endpoint(
    creator_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await untrack_creator(db, team, creator_id)


@router.get(
    "/{creator_id}",
    response_model=CreatorDetailResponse,
    summary="Get creator detail with recent snapshots",
)
async def get_creator_endpoint(
    creator_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreatorDetailResponse:
    return await get_creator_detail(db, team, creator_id)
