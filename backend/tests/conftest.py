"""Shared pytest fixtures."""

import asyncio
import sys

import pytest
from httpx import ASGITransport, AsyncClient

# Windows fix: asyncpg doesn't work with the default ProactorEventLoop on Windows.
# Switch to SelectorEventLoopPolicy globally before pytest-asyncio creates loops.
# See: https://github.com/MagicStack/asyncpg/issues/1051
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client for testing FastAPI endpoints in-process.

    - Triggers FastAPI lifespan (builds DataProviderRouter into app.state)
    - Disposes the SQLAlchemy engine after each test so each new event loop
      gets a fresh asyncpg connection pool (avoids 'NoneType.send' on Windows)
    """
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
    # Dispose engine so the next test (with a new event loop) gets fresh connections
    await engine.dispose()
