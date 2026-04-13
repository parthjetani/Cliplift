"""Analytics routes — dashboard metrics + detail page timelines.

All endpoints are auth-required and team-scoped. Results are cached for 5
minutes via the generic cache helper to avoid redundant DB queries when a user
refreshes the dashboard repeatedly.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    CreatorTimelineResponse,
    NichePerformanceResponse,
    OverviewResponse,
    RecentOutliersResponse,
    VideoTimelineResponse,
)
from app.analytics.service import (
    get_creator_timeline,
    get_niche_performance,
    get_overview,
    get_recent_outliers,
    get_video_timeline,
)
from app.auth.dependencies import get_current_team
from app.auth.models import Team
from app.common.cache import cached, invalidate
from app.database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

CACHE_TTL = 300  # 5 minutes


def _team_cache_key(team_id: uuid.UUID, suffix: str) -> str:
    return f"analytics:{team_id}:{suffix}"


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Dashboard overview stats",
)
async def overview(
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    fresh: Annotated[bool, Query(description="Bypass cache")] = False,
) -> OverviewResponse:
    cache_key = _team_cache_key(team.id, "overview")
    if fresh:
        await invalidate(cache_key)
    return await cached(
        key=cache_key,
        ttl_seconds=CACHE_TTL,
        compute=lambda: get_overview(db, team),
        serialize=lambda r: r.model_dump_json(),
        deserialize=lambda s: OverviewResponse.model_validate_json(s),
    )


@router.get(
    "/creators/{creator_id}/timeline",
    response_model=CreatorTimelineResponse,
    summary="Creator snapshot timeline for charts",
)
async def creator_timeline(
    creator_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> CreatorTimelineResponse:
    return await cached(
        key=_team_cache_key(team.id, f"creator:{creator_id}:timeline:{days}"),
        ttl_seconds=CACHE_TTL,
        compute=lambda: get_creator_timeline(db, team, creator_id, days),
        serialize=lambda r: r.model_dump_json(),
        deserialize=lambda s: CreatorTimelineResponse.model_validate_json(s),
    )


@router.get(
    "/videos/{video_id}/timeline",
    response_model=VideoTimelineResponse,
    summary="Video snapshot timeline for velocity curves",
)
async def video_timeline(
    video_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: Annotated[int, Query(ge=1, le=720)] = 72,
) -> VideoTimelineResponse:
    return await cached(
        key=_team_cache_key(team.id, f"video:{video_id}:timeline:{hours}"),
        ttl_seconds=CACHE_TTL,
        compute=lambda: get_video_timeline(db, team, video_id, hours),
        serialize=lambda r: r.model_dump_json(),
        deserialize=lambda s: VideoTimelineResponse.model_validate_json(s),
    )


@router.get(
    "/niches/{niche_id}/performance",
    response_model=NichePerformanceResponse,
    summary="Niche performance: platform breakdown + daily discovery",
)
async def niche_performance(
    niche_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> NichePerformanceResponse:
    return await cached(
        key=_team_cache_key(team.id, f"niche:{niche_id}:perf:{days}"),
        ttl_seconds=CACHE_TTL,
        compute=lambda: get_niche_performance(db, team, niche_id, days),
        serialize=lambda r: r.model_dump_json(),
        deserialize=lambda s: NichePerformanceResponse.model_validate_json(s),
    )


@router.get(
    "/recent-outliers",
    response_model=RecentOutliersResponse,
    summary="Top recent outliers across the team's niches",
)
async def recent_outliers(
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RecentOutliersResponse:
    return await cached(
        key=_team_cache_key(team.id, f"outliers:{limit}"),
        ttl_seconds=CACHE_TTL,
        compute=lambda: get_recent_outliers(db, team, limit),
        serialize=lambda r: r.model_dump_json(),
        deserialize=lambda s: RecentOutliersResponse.model_validate_json(s),
    )
