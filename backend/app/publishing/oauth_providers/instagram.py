"""Meta (Instagram) OAuth provider.

Activated when META_OAUTH_CLIENT_ID and META_OAUTH_CLIENT_SECRET are set.
Uses the Meta Graph API OAuth flow for Instagram Business accounts:
https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/getting-started
"""

import logging
from urllib.parse import urlencode

import httpx

from app.platforms.base import Platform
from app.publishing.oauth_providers.base import OAuthProvider, TokenExchangeResult

logger = logging.getLogger(__name__)

META_AUTH_URL = "https://www.facebook.com/v21.0/dialog/oauth"
META_TOKEN_URL = "https://graph.facebook.com/v21.0/oauth/access_token"
META_USERINFO_URL = "https://graph.facebook.com/v21.0/me"

INSTAGRAM_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
]


class InstagramOAuthProvider(OAuthProvider):
    """Real Meta OAuth for Instagram Business publishing."""

    platform = Platform.INSTAGRAM
    name = "meta_oauth"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": ",".join(INSTAGRAM_SCOPES),
            "response_type": "code",
            "state": state,
        }
        return f"{META_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> TokenExchangeResult:
        async with httpx.AsyncClient(timeout=10.0) as http:
            token_resp = await http.get(
                META_TOKEN_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            if token_resp.status_code != 200:
                logger.error(f"Meta token exchange failed: {token_resp.text[:200]}")
                raise ValueError("Token exchange failed")
            token_data = token_resp.json()

            userinfo_resp = await http.get(
                META_USERINFO_URL,
                params={"access_token": token_data["access_token"]},
            )
            user_data = userinfo_resp.json() if userinfo_resp.status_code == 200 else {}

        return TokenExchangeResult(
            access_token=token_data["access_token"],
            refresh_token=None,  # Meta uses long-lived tokens, not refresh tokens
            expires_in=token_data.get("expires_in"),
            scopes=INSTAGRAM_SCOPES,
            platform_user_id=user_data.get("id"),
            platform_username=user_data.get("name"),
        )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> TokenExchangeResult:
        """Refresh a Meta long-lived access token.

        Meta doesn't issue traditional refresh tokens — instead, long-lived
        access tokens (60 days) can be refreshed within their lifetime via
        `grant_type=fb_exchange_token`. We pass the *current access token* in
        the `refresh_token` parameter slot for symmetry with the OAuth ABC.

        See: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived
        """
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(
                META_TOKEN_URL,
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "fb_exchange_token": refresh_token,
                },
            )
            if resp.status_code != 200:
                logger.error(
                    f"Meta token refresh failed: {resp.text[:200]}"
                )
                raise ValueError("Token refresh failed")
            data = resp.json()

        return TokenExchangeResult(
            access_token=data["access_token"],
            refresh_token=None,
            expires_in=data.get("expires_in"),
            scopes=INSTAGRAM_SCOPES,
        )
