"""FastAPI application factory.

Wires together middleware (CORS, error handlers), routes, and lifespan events.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.ai.factory import get_ai_client
from app.analytics.routes import router as analytics_router
from app.billing.factory import build_stripe_client
from app.billing.routes import router as billing_router
from app.auth.routes import router as auth_router
from app.common.errors import register_error_handlers
from app.common.storage import build_storage
from app.config import settings
from app.creators.routes import router as creators_router
from app.discovery.niche_routes import router as niches_router
from app.discovery.routes import router as discovery_router
from app.platforms.factory import build_router as build_data_router
from app.publishing.oauth_routes import router as oauth_router
from app.publishing.publishers.factory import build_publisher_router
from app.publishing.routes import router as publishing_router
from app.videos.routes import router as videos_router
from app.workers.routes import router as workers_router

# --- Logging setup ---
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cliplift")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup + shutdown hooks."""
    logger.info(
        f"Starting {settings.APP_NAME} v{__version__} "
        f"in {settings.ENVIRONMENT} mode"
    )
    logger.info(f"CORS origins: {settings.cors_origins_list}")

    # Fail fast if ENCRYPTION_KEY is missing in production — OAuth tokens
    # would be unencryptable, and the error would only surface on first
    # OAuth connect (hours after deploy). Better to crash at startup.
    if settings.is_production and not settings.ENCRYPTION_KEY:
        raise RuntimeError(
            "ENCRYPTION_KEY is required in production. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )

    # Log which integrations are mocked vs live
    integrations = {
        "YouTube": bool(settings.YOUTUBE_API_KEY),
        "Netrows (LinkedIn)": bool(settings.NETROWS_API_KEY),
        "Data365 (TikTok/IG)": bool(settings.DATA365_API_KEY),
        "Stripe": bool(settings.STRIPE_SECRET_KEY),
        "Resend": bool(settings.RESEND_API_KEY),
        "Upstash Redis": bool(settings.UPSTASH_REDIS_REST_URL),
        "Supabase Storage": bool(settings.SUPABASE_SERVICE_ROLE_KEY),
    }
    for name, is_live in integrations.items():
        status = "LIVE" if is_live else "MOCK"
        logger.info(f"  [{status}] {name}")

    # Build the DataProviderRouter once and stash it on app.state.
    # Routes pull it via Depends(get_router_from_app).
    app.state.data_provider_router = build_data_router(settings)

    # Build the AI client (real Claude or mock based on ANTHROPIC_API_KEY)
    app.state.ai_client = get_ai_client(settings)

    # Build the storage backend (Supabase Storage or local disk fallback)
    app.state.storage = build_storage(settings)

    # Build the PublisherRouter (real YouTube + Instagram, mock for the rest)
    app.state.publisher_router = build_publisher_router(settings)

    # Build the Stripe client (real or mock based on STRIPE_SECRET_KEY)
    app.state.stripe_client = build_stripe_client(settings)

    yield

    logger.info("Closing connections...")
    await app.state.data_provider_router.close()
    await app.state.publisher_router.close()
    if hasattr(app.state.storage, "close"):
        await app.state.storage.close()
    logger.info(f"Shutting down {settings.APP_NAME}")


# --- FastAPI app ---
app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description="Cliplift API — short-form video analytics + publishing",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Error handlers ---
register_error_handlers(app)


# --- Health check (used by Railway + QStash warm-up pings) ---
@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Used by:
    - Railway for liveness probes
    - QStash to warm up the server before triggering workers (avoids cold start
      timeout when Railway auto-sleep is enabled)
    """
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": __version__,
    }


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Root endpoint — points to docs."""
    return {
        "name": settings.APP_NAME,
        "version": __version__,
        "docs": "/docs",
    }


# --- API routes ---
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(discovery_router, prefix=settings.API_V1_PREFIX)
app.include_router(creators_router, prefix=settings.API_V1_PREFIX)
app.include_router(videos_router, prefix=settings.API_V1_PREFIX)
app.include_router(niches_router, prefix=settings.API_V1_PREFIX)
app.include_router(workers_router, prefix=settings.API_V1_PREFIX)
app.include_router(oauth_router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(publishing_router, prefix=settings.API_V1_PREFIX)
app.include_router(billing_router, prefix=settings.API_V1_PREFIX)
