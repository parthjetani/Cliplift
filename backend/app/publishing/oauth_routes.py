"""OAuth platform connection routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_team
from app.auth.models import Team
from app.billing.enforcement import enforce_platform_connection_limit, require_active_plan
from app.config import settings
from app.database import get_db
from app.platforms.base import Platform
from app.publishing.oauth_schemas import AuthorizeResponse, ConnectionResponse
from app.publishing.oauth_service import (
    complete_callback,
    delete_connection,
    list_connections,
    start_authorize,
)

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get(
    "",
    response_model=list[ConnectionResponse],
    summary="List connected platform accounts for the current team",
)
async def list_connections_endpoint(
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ConnectionResponse]:
    return await list_connections(db, team)


@router.post(
    "/{platform}/authorize",
    response_model=AuthorizeResponse,
    summary="Begin OAuth flow for a platform",
    description=(
        "Returns an authorize_url for the user's browser to visit. After consent, "
        "the provider redirects back to /connections/{platform}/callback, which "
        "completes the flow and creates a PlatformConnection."
    ),
)
async def authorize_endpoint(
    platform: Platform,
    team: Annotated[Team, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthorizeResponse:
    await enforce_platform_connection_limit(db, team)
    return await start_authorize(team, platform)


@router.get(
    "/{platform}/callback",
    summary="OAuth callback — completes the connection",
    description=(
        "Called by the OAuth provider after the user grants consent. "
        "Validates the state, exchanges the code for tokens, encrypts and "
        "persists them, then redirects the user to /dashboard/settings/connections."
    ),
)
async def callback_endpoint(
    platform: Platform,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    # Note: this endpoint does NOT use get_current_team — the user isn't sending
    # an Authorization header here (they're being redirected from Google/Meta).
    # The state token is what authorizes the request, not a JWT.
    await complete_callback(db, platform, code, state)
    # IMPORTANT: must be an absolute URL pointing at the FRONTEND host, not a
    # relative path. The browser is currently on the API host (we just received
    # a server-to-browser redirect from Google/Meta back to our /callback), so
    # a relative URL would resolve against the API host, not the frontend.
    redirect_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/dashboard/settings/connections?connected=1"
    )
    return RedirectResponse(
        url=redirect_url,
        status_code=status.HTTP_302_FOUND,
    )


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a platform account",
)
async def delete_connection_endpoint(
    connection_id: uuid.UUID,
    team: Annotated[Team, Depends(get_current_team)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await delete_connection(db, team, connection_id)
