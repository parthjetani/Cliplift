"""Worker route definitions — HTTP endpoints triggered by QStash (or curl in dev).

All workers accept an optional `max_age_hours` query parameter that overrides
the default cutoff. Pass `max_age_hours=0` to force-process all rows regardless
of last_scraped_at — useful for manual dev triggers and tests.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.storage import StorageBackend
from app.database import get_db
from app.platforms.router import DataProviderRouter
from app.publishing.publisher_router import PublisherRouter
from app.workers.collect_analytics import collect_analytics
from app.workers.discover_trends import discover_trends
from app.workers.middleware import verify_qstash_signature
from app.workers.publish_scheduled import publish_scheduled
from app.workers.scrape_creators import scrape_creators
from app.workers.scrape_videos import scrape_videos

router = APIRouter(
    prefix="/workers",
    tags=["workers"],
    dependencies=[Depends(verify_qstash_signature)],
)


def get_router_from_app(request: Request) -> DataProviderRouter:
    return request.app.state.data_provider_router


def get_storage_from_app(request: Request) -> StorageBackend:
    return request.app.state.storage


def get_publisher_router_from_app(request: Request) -> PublisherRouter:
    return request.app.state.publisher_router


@router.post(
    "/scrape-creators",
    summary="[QStash] Daily refresh of tracked creator metrics",
)
async def scrape_creators_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    provider_router: Annotated[DataProviderRouter, Depends(get_router_from_app)],
    max_age_hours: Annotated[int, Query(ge=0, le=720)] = 24,
) -> dict:
    return await scrape_creators(db, provider_router, max_age_hours=max_age_hours)


@router.post(
    "/scrape-videos",
    summary="[QStash] 6-hourly refresh of tracked video metrics + view velocity",
)
async def scrape_videos_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    provider_router: Annotated[DataProviderRouter, Depends(get_router_from_app)],
    max_age_hours: Annotated[int, Query(ge=0, le=720)] = 6,
) -> dict:
    return await scrape_videos(db, provider_router, max_age_hours=max_age_hours)


@router.post(
    "/discover-trends",
    summary="[QStash] Hourly auto-discovery for all active niches",
)
async def discover_trends_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    provider_router: Annotated[DataProviderRouter, Depends(get_router_from_app)],
    max_age_hours: Annotated[int, Query(ge=0, le=720)] = 1,
) -> dict:
    return await discover_trends(db, provider_router, max_age_hours=max_age_hours)


@router.post(
    "/publish-scheduled",
    summary="[QStash, 5min cron, 120s timeout] Publish due scheduled posts",
)
async def publish_scheduled_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_from_app)],
    publisher_router: Annotated[
        PublisherRouter, Depends(get_publisher_router_from_app)
    ],
    max_posts: Annotated[int, Query(ge=1, le=10)] = 1,
) -> dict:
    return await publish_scheduled(
        db, storage, publisher_router, max_posts=max_posts
    )


@router.post(
    "/collect-analytics",
    summary="[QStash, daily] Collect performance metrics for published posts",
)
async def collect_analytics_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    provider_router: Annotated[DataProviderRouter, Depends(get_router_from_app)],
    max_age_hours: Annotated[int, Query(ge=0, le=720)] = 24,
) -> dict:
    return await collect_analytics(db, provider_router, max_age_hours=max_age_hours)
