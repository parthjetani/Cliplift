"""Shared credential refresh flow used by every real publisher.

The publish worker calls `get_fresh_access_token(...)` right before pushing
to the platform's API. If the connection's access token is expired (or close
to expiring), this helper:

1. Decrypts the refresh token
2. Calls the OAuth provider's `refresh_access_token` flow
3. Persists the new encrypted tokens + expiry back to the `PlatformConnection`
4. Returns the plaintext access token for the caller to use immediately

The plaintext token never touches the database — only the publisher's
in-memory call holds it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.encryption import decrypt_token, encrypt_token
from app.publishing.models import PlatformConnection
from app.publishing.oauth_providers.base import OAuthProvider
from app.publishing.publishers.base import PublisherError

logger = logging.getLogger(__name__)


# Refresh tokens this many seconds *before* they actually expire so the
# fresh token doesn't time out mid-API-call. Five minutes is generous.
REFRESH_SAFETY_MARGIN = timedelta(minutes=5)


async def get_fresh_access_token(
    db: AsyncSession,
    connection: PlatformConnection,
    oauth_provider: OAuthProvider,
) -> str:
    """Return a guaranteed-fresh access token, refreshing it if needed.

    Side effect: if a refresh happened, the new encrypted tokens and the new
    `token_expires_at` are committed to the database before this function
    returns.

    Raises:
        PublisherError: If the connection has no access token, or the refresh
            flow fails (e.g., refresh token revoked).
    """
    if not connection.access_token:
        raise PublisherError(
            f"Connection {connection.id} has no access token stored"
        )

    now = datetime.now(timezone.utc)
    needs_refresh = (
        connection.token_expires_at is not None
        and connection.token_expires_at - REFRESH_SAFETY_MARGIN <= now
    )

    if not needs_refresh:
        return decrypt_token(connection.access_token)

    if not connection.refresh_token:
        raise PublisherError(
            f"Connection {connection.id} access token is expired and "
            f"no refresh token is available — user must reconnect"
        )

    logger.info(
        f"Refreshing access token for connection {connection.id} "
        f"({connection.platform})"
    )
    plaintext_refresh = decrypt_token(connection.refresh_token)
    try:
        refreshed = await oauth_provider.refresh_access_token(plaintext_refresh)
    except ValueError as e:
        raise PublisherError(
            f"Failed to refresh access token for connection {connection.id}: {e}"
        ) from e

    connection.access_token = encrypt_token(refreshed.access_token)
    if refreshed.refresh_token:
        connection.refresh_token = encrypt_token(refreshed.refresh_token)
    if refreshed.expires_in:
        connection.token_expires_at = now + timedelta(
            seconds=refreshed.expires_in
        )

    db.add(connection)
    await db.commit()
    await db.refresh(connection)

    return refreshed.access_token
