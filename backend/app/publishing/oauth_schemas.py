"""Pydantic schemas for OAuth platform connection flows."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.platforms.base import Platform


class AuthorizeResponse(BaseModel):
    """POST /connections/{platform}/authorize → returns the URL the user must visit."""

    authorize_url: str
    state: str
    platform: Platform


class ConnectionResponse(BaseModel):
    """A connected platform account.

    Tokens are NEVER returned — only metadata. The encrypted ciphertexts live
    in the DB and are only decrypted server-side when publishing.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: Platform
    platform_user_id: str | None = None
    platform_username: str | None = None
    scopes: list[str] | None = None
    token_expires_at: datetime | None = None
    connected_at: datetime
    is_expired: bool = False


class CallbackResult(BaseModel):
    """Internal type returned by oauth_service.complete_callback()."""

    connection: ConnectionResponse
    redirect_to: str = "/dashboard/settings/connections"
