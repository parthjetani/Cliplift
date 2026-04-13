"""Application settings loaded from environment variables.

All external service keys are OPTIONAL — missing keys trigger mock fallbacks
so the full stack runs end-to-end without paying for any service.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Reads from environment variables and `.env` file. All external service keys
    are optional and default to empty strings — adapters check for presence and
    fall back to mock implementations when keys are missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    APP_NAME: str = "Cliplift"
    API_V1_PREFIX: str = "/api/v1"

    # --- Backend server ---
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"
    )

    # --- Supabase Auth ---
    SUPABASE_URL: str = "http://127.0.0.1:54321"
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = (
        "super-secret-jwt-token-with-at-least-32-characters-long"
    )

    # --- Upstash (Redis + QStash) ---
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""
    QSTASH_TOKEN: str = ""
    QSTASH_CURRENT_SIGNING_KEY: str = ""
    QSTASH_NEXT_SIGNING_KEY: str = ""

    # --- Data Providers (all optional, mock fallback when empty) ---
    YOUTUBE_API_KEY: str = ""
    NETROWS_API_KEY: str = ""
    DATA365_API_KEY: str = ""

    # --- Stripe ---
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_CREATOR: str = ""
    STRIPE_PRICE_TEAM: str = ""
    STRIPE_PRICE_AGENCY: str = ""

    # --- Resend ---
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "alerts@cliplift.com"

    # --- Storage (Supabase Storage in prod, local disk in dev) ---
    # `auto` = Supabase Storage iff ENVIRONMENT=production AND SUPABASE_SERVICE_ROLE_KEY,
    #         otherwise local disk. Override with STORAGE_BACKEND=supabase to force
    #         Supabase in dev (e.g., for an integration test against a real bucket).
    STORAGE_BACKEND: Literal["auto", "local", "supabase"] = "auto"
    SUPABASE_STORAGE_BUCKET: str = "cliplift-videos"
    LOCAL_STORAGE_DIR: str = "./uploads"
    LOCAL_STORAGE_PUBLIC_BASE_URL: str = "http://localhost:8000"

    # --- OAuth: YouTube (Google) ---
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""

    # --- OAuth: Instagram (Meta) ---
    META_OAUTH_CLIENT_ID: str = ""
    META_OAUTH_CLIENT_SECRET: str = ""

    # Where OAuth providers should redirect after user consent.
    # Defaults to local dev — production should override.
    OAUTH_REDIRECT_BASE_URL: str = "http://localhost:8000/api/v1/connections"

    # Frontend host — used for redirect URLs that take the user back to the
    # browser app (e.g., after OAuth callback). Must be the public-facing URL
    # of the Next.js frontend, NOT the backend API host.
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Anthropic (AI content briefs) ---
    ANTHROPIC_API_KEY: str = ""

    # --- Sentry ---
    SENTRY_DSN: str = ""

    # --- Encryption (OAuth token storage) ---
    # 32-byte URL-safe base64 key. Generate via:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # EMPTY by default — production MUST set this. Dev/tests use the value from .env.example.
    ENCRYPTION_KEY: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS comma-separated string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
