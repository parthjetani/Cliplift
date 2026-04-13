"""Videos routes — track, untrack, list, detail."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_team
from app.auth.models import Team
from app.common.pagination import PaginatedResponse
from app.common.ratelimit import rate_limit
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params
from app.platforms.router import DataProviderRouter
from app.videos.schemas import (
    TrackedVideoResponse,
    TrackVideoRequest,
    VideoDetailResponse,
)
from app.videos.service import (
    get_video_detail,
    list_tracked_videos,
    track_video,
    untrack_video,
)

router = APIRouter(prefix="/videos", tags=["videos"])


def get_router_from_app(request: Request) -> DataProviderRouter:
    return request.app.state.data_provider_router


@router.get(
    "",
    response_model=PaginatedResponse[TrackedVideoResponse],
    summary="List tracked videos",
)
async def list_videos(
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> PaginatedResponse[TrackedVideoResponse]:
    return await list_tracked_videos(db, team, pagination)


@router.post(
    "/track",
    response_model=TrackedVideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Track a new video",
    dependencies=[Depends(rate_limit("track_video", max_requests=30, window_seconds=60))],
)
async def track_video_endpoint(
    body: TrackVideoRequest,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    router: Annotated[DataProviderRouter, Depends(get_router_from_app)],
) -> TrackedVideoResponse:
    try:
        platform, platform_video_id = body.resolve()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    return await track_video(
        db=db,
        team=team,
        platform=platform,
        platform_video_id=platform_video_id,
        router=router,
    )


@router.delete(
    "/{video_id}/untrack",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Untrack a video",
)
async def untrack_video_endpoint(
    video_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await untrack_video(db, team, video_id)


@router.get(
    "/{video_id}",
    response_model=VideoDetailResponse,
    summary="Get video detail with recent snapshots",
)
async def get_video_endpoint(
    video_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VideoDetailResponse:
    return await get_video_detail(db, team, video_id)
