"""Abstract OAuthProvider interface.

Every provider implementation (Google, Meta, Mock, etc.) returns the same
shape from `exchange_code()` and `refresh_access_token()` so the rest of the
OAuth + publishing flow is platform-agnostic.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.platforms.base import Platform


class TokenExchangeResult(BaseModel):
    """Normalized response from an OAuth provider's token exchange or refresh.

    `expires_in` is seconds until access_token expires (per OAuth2 spec).
    `scopes` is the granted scope list (may differ from what we requested).
    `refresh_token` may be None on a refresh response — providers that rotate
    refresh tokens (Google, sometimes) include it; ones that don't (Meta) don't.
    """

    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    scopes: list[str] = []
    platform_user_id: str | None = None
    platform_username: str | None = None


class OAuthProvider(ABC):
    """Abstract base for OAuth providers."""

    platform: Platform
    name: str

    @abstractmethod
    def authorize_url(self, state: str, redirect_uri: str) -> str:
        """Build the URL the user must visit to grant consent.

        Args:
            state: CSRF token bound to the user's request (server-generated)
            redirect_uri: Where the provider should redirect after consent

        Returns:
            Full URL ready for the browser
        """

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> TokenExchangeResult:
        """Exchange an auth code for access + refresh tokens.

        Raises:
            ValueError: On invalid/expired code or provider error
        """

    @abstractmethod
    async def refresh_access_token(
        self, refresh_token: str
    ) -> TokenExchangeResult:
        """Mint a new access token from a refresh token.

        Called by the publisher just before publishing if the connection's
        `token_expires_at` is in the past. The returned `TokenExchangeResult`
        replaces the connection's `access_token` (and `refresh_token` if the
        provider rotated it) and `token_expires_at`.

        Args:
            refresh_token: The plaintext refresh token (decrypted by caller)

        Returns:
            A TokenExchangeResult with at least `access_token` and `expires_in`.

        Raises:
            ValueError: On invalid/revoked refresh token or provider error.
        """
