"""Google OAuth provider for YouTube uploads.

Activated when GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are set.
Otherwise the factory falls back to MockOAuthProvider.

Uses the Google OAuth 2.0 web server flow:
https://developers.google.com/identity/protocols/oauth2/web-server
"""

import logging
from urllib.parse import urlencode

import httpx

from app.platforms.base import Platform
from app.publishing.oauth_providers.base import OAuthProvider, TokenExchangeResult

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


class YouTubeOAuthProvider(OAuthProvider):
    """Real Google OAuth for YouTube."""

    platform = Platform.YOUTUBE
    name = "google_oauth"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(YOUTUBE_SCOPES),
            "access_type": "offline",  # required for refresh_token
            "prompt": "consent",  # forces refresh_token issuance on every consent
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> TokenExchangeResult:
        async with httpx.AsyncClient(timeout=10.0) as http:
            token_resp = await http.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                logger.error(f"Google token exchange failed: {token_resp.text[:200]}")
                raise ValueError("Token exchange failed")
            token_data = token_resp.json()

            # Fetch user info to populate platform_username
            userinfo_resp = await http.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            user_data = userinfo_resp.json() if userinfo_resp.status_code == 200 else {}

        return TokenExchangeResult(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
            scopes=token_data.get("scope", "").split() if token_data.get("scope") else [],
            platform_user_id=user_data.get("id"),
            platform_username=user_data.get("email"),
        )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> TokenExchangeResult:
        """Mint a new access token using Google's refresh_token grant.

        Google may or may not rotate the refresh_token in the response — if
        absent, we keep the existing one.
        """
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code != 200:
                logger.error(
                    f"Google token refresh failed: {resp.text[:200]}"
                )
                raise ValueError("Token refresh failed")
            data = resp.json()

        return TokenExchangeResult(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in"),
            scopes=data.get("scope", "").split() if data.get("scope") else [],
        )
