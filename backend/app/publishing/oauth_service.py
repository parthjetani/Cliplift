"""OAuth service — orchestrates authorize, callback, list, delete."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Team
from app.common.encryption import decrypt_token, encrypt_token
from app.config import settings
from app.platforms.base import Platform
from app.publishing.models import PlatformConnection
from app.publishing.oauth_factory import get_oauth_provider
from app.publishing.oauth_schemas import AuthorizeResponse, ConnectionResponse
from app.publishing.oauth_state import (
    generate_state,
    retrieve_state,
    store_state,
)

logger = logging.getLogger(__name__)


def _redirect_uri_for(platform: Platform) -> str:
    """The callback URL the OAuth provider should redirect to."""
    return f"{settings.OAUTH_REDIRECT_BASE_URL}/{platform.value}/callback"


async def start_authorize(
    team: Team, platform: Platform
) -> AuthorizeResponse:
    """Generate a state token, store it, and return the provider's authorize URL."""
    state = generate_state()
    await store_state(
        state,
        {
            "team_id": str(team.id),
            "platform": platform.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    provider = get_oauth_provider(platform, settings)
    redirect_uri = _redirect_uri_for(platform)
    authorize_url = provider.authorize_url(state=state, redirect_uri=redirect_uri)

    return AuthorizeResponse(
        authorize_url=authorize_url,
        state=state,
        platform=platform,
    )


async def complete_callback(
    db: AsyncSession,
    platform: Platform,
    code: str,
    state: str,
) -> ConnectionResponse:
    """Exchange the auth code for tokens, encrypt, and persist a PlatformConnection.

    Validates the state token belongs to the platform we're completing for.
    """
    payload = await retrieve_state(state)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    if payload.get("platform") != platform.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State / platform mismatch",
        )

    team_id = uuid.UUID(payload["team_id"])

    # Exchange code → tokens
    provider = get_oauth_provider(platform, settings)
    redirect_uri = _redirect_uri_for(platform)
    try:
        result = await provider.exchange_code(code=code, redirect_uri=redirect_uri)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token exchange failed: {e}",
        )

    expires_at = None
    if result.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=result.expires_in)

    # Encrypt tokens before DB write — DB never sees plaintext
    access_ciphertext = encrypt_token(result.access_token)
    refresh_ciphertext = encrypt_token(result.refresh_token) if result.refresh_token else None

    # Idempotent upsert: one connection per (team, platform, platform_user_id)
    existing_q = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.team_id == team_id,
            PlatformConnection.platform == platform.value,
            PlatformConnection.platform_user_id == result.platform_user_id,
        )
    )
    connection = existing_q.scalar_one_or_none()

    if connection:
        connection.access_token = access_ciphertext
        connection.refresh_token = refresh_ciphertext
        connection.token_expires_at = expires_at
        connection.scopes = result.scopes
        connection.platform_username = result.platform_username
        connection.connected_at = datetime.now(timezone.utc)
    else:
        connection = PlatformConnection(
            team_id=team_id,
            platform=platform.value,
            platform_user_id=result.platform_user_id,
            platform_username=result.platform_username,
            access_token=access_ciphertext,
            refresh_token=refresh_ciphertext,
            token_expires_at=expires_at,
            scopes=result.scopes,
            connected_at=datetime.now(timezone.utc),
        )
        db.add(connection)

    await db.commit()
    await db.refresh(connection)

    return _to_response(connection)


async def list_connections(
    db: AsyncSession, team: Team
) -> list[ConnectionResponse]:
    """List all platform connections for a team."""
    result = await db.execute(
        select(PlatformConnection)
        .where(PlatformConnection.team_id == team.id)
        .order_by(PlatformConnection.connected_at.desc())
    )
    return [_to_response(c) for c in result.scalars().all()]


async def delete_connection(
    db: AsyncSession, team: Team, connection_id: uuid.UUID
) -> None:
    """Delete a connection. Raises 404 if not found / wrong team."""
    result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.id == connection_id,
            PlatformConnection.team_id == team.id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    await db.delete(connection)
    await db.commit()


def _to_response(connection: PlatformConnection) -> ConnectionResponse:
    """Convert a PlatformConnection ORM row to a public response (no tokens)."""
    is_expired = False
    if connection.token_expires_at:
        is_expired = connection.token_expires_at < datetime.now(timezone.utc)

    return ConnectionResponse(
        id=connection.id,
        platform=Platform(connection.platform),
        platform_user_id=connection.platform_user_id,
        platform_username=connection.platform_username,
        scopes=connection.scopes,
        token_expires_at=connection.token_expires_at,
        connected_at=connection.connected_at,
        is_expired=is_expired,
    )


async def get_decrypted_access_token(
    connection: PlatformConnection,
) -> str:
    """Decrypt the access token for use by the publishing worker.

    NEVER expose this through the API — only call from server-side publishing code.
    """
    return decrypt_token(connection.access_token)
