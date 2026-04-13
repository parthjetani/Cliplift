"""Publishing routes — presign + scheduled post CRUD.

Mounted at `/api/v1/publishing/...` (the OAuth flow lives separately at
`/api/v1/connections/...` via `oauth_routes.py` because connections are
top-level, not nested under publishing).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_profile, get_current_team
from app.auth.models import Profile, Team
from app.billing.enforcement import enforce_scheduling_enabled, require_active_plan
from app.common.pagination import PaginatedResponse
from app.common.ratelimit import rate_limit
from app.common.storage import LocalStorageBackend, StorageBackend
from app.database import get_db
from app.dependencies import PaginationParams, pagination_params
from app.publishing.schemas import (
    PostStatus,
    PresignRequest,
    PresignResponse,
    ScheduledPostCreate,
    ScheduledPostResponse,
    ScheduledPostUpdate,
)
from app.publishing.service import (
    create_scheduled_post,
    delete_scheduled_post,
    get_scheduled_post,
    list_scheduled_posts,
    presign_upload,
    update_scheduled_post,
)

router = APIRouter(prefix="/publishing", tags=["publishing"])


def get_storage(request: Request) -> StorageBackend:
    """Pull the StorageBackend off `app.state` (set in main.py lifespan)."""
    return request.app.state.storage


# ----------------------------------------------------------------------------
# Presign
# ----------------------------------------------------------------------------


@router.post(
    "/uploads/presign",
    response_model=PresignResponse,
    summary="Generate a presigned upload URL for a video file",
    description=(
        "Returns a URL the browser can PUT a video to directly. The video "
        "never touches the FastAPI server. The returned `file_key` is what "
        "you pass to `POST /scheduled-posts` to attach the uploaded file."
    ),
    dependencies=[Depends(rate_limit("publish_presign", 20, 3600))],
)
async def presign_upload_endpoint(
    payload: PresignRequest,
    team: Annotated[Team, Depends(require_active_plan)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> PresignResponse:
    enforce_scheduling_enabled(team)
    return await presign_upload(storage, team, payload)


# ----------------------------------------------------------------------------
# Scheduled post CRUD
# ----------------------------------------------------------------------------


@router.post(
    "/scheduled-posts",
    response_model=ScheduledPostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a scheduled post",
)
async def create_post_endpoint(
    payload: ScheduledPostCreate,
    team: Annotated[Team, Depends(require_active_plan)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScheduledPostResponse:
    enforce_scheduling_enabled(team)
    return await create_scheduled_post(db, team, profile, payload)


@router.get(
    "/scheduled-posts",
    response_model=PaginatedResponse[ScheduledPostResponse],
    summary="List the team's scheduled posts (cursor-paginated)",
)
async def list_posts_endpoint(
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    status_filter: Annotated[
        PostStatus | None,
        Query(alias="status", description="Filter by post status"),
    ] = None,
) -> PaginatedResponse[ScheduledPostResponse]:
    return await list_scheduled_posts(db, team, pagination, status_filter)


@router.get(
    "/scheduled-posts/{post_id}",
    response_model=ScheduledPostResponse,
    summary="Get a single scheduled post",
)
async def get_post_endpoint(
    post_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScheduledPostResponse:
    return await get_scheduled_post(db, team, post_id)


@router.patch(
    "/scheduled-posts/{post_id}",
    response_model=ScheduledPostResponse,
    summary="Update a scheduled post (only draft / scheduled / failed are editable)",
)
async def update_post_endpoint(
    post_id: uuid.UUID,
    payload: ScheduledPostUpdate,
    team: Annotated[Team, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScheduledPostResponse:
    return await update_scheduled_post(db, team, post_id, payload)


@router.delete(
    "/scheduled-posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scheduled post and its file",
)
async def delete_post_endpoint(
    post_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await delete_scheduled_post(db, team, storage, post_id)


# ----------------------------------------------------------------------------
# Local-storage upload sink (dev only)
# ----------------------------------------------------------------------------
#
# The browser uploads bytes here when the storage backend is LocalStorageBackend
# (i.e., dev environments without Supabase Storage). In production this route
# exists but returns 404 because the storage backend is SupabaseStorageBackend
# and the browser uploads directly to Supabase's signed URL.
#
# The file_key acts as the auth token: it embeds a `<team_uuid>/<random_uuid>/`
# prefix that's only known to the user who just called /uploads/presign. This
# is the same security model as a presigned URL — guessing both UUIDs is
# infeasible.


@router.put(
    "/uploads/local/{file_key:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
    summary="[dev only] PUT sink for LocalStorageBackend uploads",
)
async def local_upload_sink(
    file_key: str,
    request: Request,
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> Response:
    if not isinstance(storage, LocalStorageBackend):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local upload sink not available in this environment",
        )
    body = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream")
    await storage.write_bytes(file_key, body, content_type=content_type)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/uploads/local/{file_key:path}",
    include_in_schema=False,
    summary="[dev only] GET sink for LocalStorageBackend downloads",
)
async def local_download_sink(
    file_key: str,
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> Response:
    if not isinstance(storage, LocalStorageBackend):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local download sink not available in this environment",
        )
    try:
        data = await storage.download_bytes(file_key)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from e
    return Response(content=data, media_type="video/mp4")
