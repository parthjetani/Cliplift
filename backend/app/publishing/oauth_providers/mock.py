"""Mock OAuth provider — completes the flow without real credentials.

Used automatically when GOOGLE_OAUTH_CLIENT_ID / META_OAUTH_CLIENT_ID are not
set in the environment. Lets the entire end-to-end flow be exercised in tests
and local dev:

    POST /api/v1/connections/youtube/authorize
        → returns http://localhost:8000/api/v1/connections/youtube/callback?code=...&state=...
    GET  ↑ that URL                              (browser would auto-redirect)
        → exchange_code returns deterministic fake tokens
    PlatformConnection row inserted with encrypted (fake) tokens
"""

import hashlib
from urllib.parse import urlencode

from app.publishing.oauth_providers.base import OAuthProvider, TokenExchangeResult
from app.platforms.base import Platform


class MockOAuthProvider(OAuthProvider):
    """Returns a self-callback URL and deterministic fake tokens."""

    name = "mock"

    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        # The "consent screen" is just our own callback URL with a fake code.
        # In production this would be Google/Meta's actual OAuth consent page.
        params = {"code": f"mock-code-{state[:16]}", "state": state}
        return f"{redirect_uri}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> TokenExchangeResult:
        if not code.startswith("mock-code-"):
            raise ValueError("Mock provider only accepts mock-code-* codes")

        # Deterministic fake user data based on the code
        digest = hashlib.md5(code.encode()).hexdigest()[:8]
        return TokenExchangeResult(
            access_token=f"mock-access-{digest}",
            refresh_token=f"mock-refresh-{digest}",
            expires_in=3600,
            scopes=self._mock_scopes(),
            platform_user_id=f"mock-user-{digest}",
            platform_username=f"{self.platform.value}_user_{digest}",
        )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> TokenExchangeResult:
        """Mock refresh — deterministic new access token, never fails.

        Encodes the input refresh_token in the new access_token so tests can
        assert the refresh path was taken (e.g., new token != old token).
        """
        if not refresh_token:
            raise ValueError("Mock refresh requires a non-empty refresh_token")
        digest = hashlib.md5(f"refreshed-{refresh_token}".encode()).hexdigest()[:8]
        return TokenExchangeResult(
            access_token=f"mock-access-refreshed-{digest}",
            refresh_token=refresh_token,  # Mock doesn't rotate
            expires_in=3600,
            scopes=self._mock_scopes(),
        )

    def _mock_scopes(self) -> list[str]:
        return {
            Platform.YOUTUBE: [
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.readonly",
            ],
            Platform.INSTAGRAM: [
                "instagram_basic",
                "instagram_content_publish",
            ],
            Platform.LINKEDIN: ["w_member_social", "r_basicprofile"],
            Platform.TIKTOK: ["video.upload", "user.info.basic"],
        }.get(self.platform, [])
