"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


# Async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_development and settings.LOG_LEVEL == "DEBUG",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    Ensures proper cleanup via context manager — session is always closed even
    if an exception is raised in the route handler.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def import_all_models() -> None:
    """Import every model module so Alembic autogenerate sees them.

    This MUST be called before Alembic introspects metadata. Called from
    alembic/env.py and from main.py at startup (harmless to call twice).
    """
    # noqa: F401 — these imports register the models with Base.metadata
    from app.auth import models as _auth  # noqa: F401
    from app.creators import models as _creators  # noqa: F401
    from app.discovery import models as _discovery  # noqa: F401
    from app.publishing import models as _publishing  # noqa: F401
    from app.videos import models as _videos  # noqa: F401
