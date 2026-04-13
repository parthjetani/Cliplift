# Testing

> 299 backend tests. pytest-asyncio with `asyncio_mode = "auto"`. All tests run against local Supabase Postgres — no mocked DB.

## Running tests

```bash
# Full suite
make test                                    # or: cd backend && uv run pytest -v

# Single file
cd backend && uv run pytest tests/test_analytics.py -v

# Single test
cd backend && uv run pytest tests/test_enforcement.py::TestCreatorTrackingLimit::test_creator_tier_blocks_4th -v

# With coverage
cd backend && uv run pytest --cov=app --cov-report=term-missing
```

**Prerequisites:** Local Supabase must be running (`make supabase-start`). Tests create real `auth.users` rows via the Supabase REST API.

## Test configuration

`backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"        # No @pytest.mark.asyncio needed
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short --strict-markers"
```

## Fixtures

### `client` (conftest.py)

Async HTTP client for testing FastAPI endpoints in-process:

```python
@pytest.fixture
async def client() -> AsyncClient:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    await engine.dispose()  # Clean pool for next test's event loop
```

- Triggers the FastAPI lifespan (builds DataProviderRouter, AIClient, storage, etc. into `app.state`)
- `engine.dispose()` after each test prevents asyncpg "attached to a different loop" errors

### `authed_user` (test_creators.py)

Creates a real Supabase user and returns `(user_id, email, headers)`:

```python
@pytest.fixture
async def authed_user() -> tuple[str, str, dict]:
    user_id, email, token = await _create_real_user()
    return user_id, email, {"Authorization": f"Bearer {token}"}
```

`_create_real_user()` signs up via `POST http://127.0.0.1:54321/auth/v1/signup` with a timestamped email. Returns a real JWT. Import it in any test file:

```python
from tests.test_creators import _create_real_user, authed_user  # noqa: F401
```

### `_upgrade_team_plan` (test_creators.py)

Upgrades a test team to a given plan via direct DB update. Needed because plan enforcement (Chunk 24) blocks scheduling and multi-platform connections on Creator tier:

```python
await _upgrade_team_plan(client, headers, "team")
```

### `db_session` (test_publish_worker.py)

Direct `AsyncSession` for tests that bypass the HTTP layer:

```python
@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        # Clear stale scheduled posts from prior runs
        await session.execute(update(ScheduledPost).where(...).values(status="draft"))
        await session.commit()
        yield session
    await engine.dispose()
```

**Critical:** any fixture that creates SQLAlchemy sessions outside conftest's `client` fixture MUST call `await engine.dispose()` in teardown.

## Test patterns

### Auth-required endpoint

```python
class TestSomethingAuth:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/some/endpoint", json={...})
        assert response.status_code == 401

class TestSomethingSuccess:
    async def test_happy_path(self, client: AsyncClient, authed_user: tuple[str, str, dict]) -> None:
        _, _, headers = authed_user
        response = await client.post("/api/v1/some/endpoint", json={...}, headers=headers)
        assert response.status_code == 201
```

### Cross-team isolation

Every new authenticated endpoint must verify that user 2 cannot access user 1's data:

```python
async def test_cross_team_isolation(self, client: AsyncClient) -> None:
    _, _, t1 = await _create_real_user()
    _, _, t2 = await _create_real_user()
    h1 = {"Authorization": f"Bearer {t1}"}
    h2 = {"Authorization": f"Bearer {t2}"}

    # User 1 creates something
    resp = await client.post("/api/v1/...", json={...}, headers=h1)
    item_id = resp.json()["id"]

    # User 2 cannot see it
    resp = await client.get(f"/api/v1/.../{item_id}", headers=h2)
    assert resp.status_code == 404
```

### Worker endpoint

```python
def dev_headers() -> dict:
    return {"X-Dev-Worker-Token": settings.ENCRYPTION_KEY}

async def test_worker_runs(self, client: AsyncClient) -> None:
    response = await client.post("/api/v1/workers/some-worker", headers=dev_headers())
    assert response.status_code == 200
```

### Mock-first integration (external API)

Never call real APIs in tests. Use `unittest.mock.patch`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

async def test_youtube_publish(self) -> None:
    mock_cls, mock_client, _ = _mock_httpx_client(json_response={"id": "yt_vid"})
    with patch("app.publishing.publishers.youtube.httpx.AsyncClient", mock_cls):
        result = await publisher.publish(...)
    assert result.platform_post_id == "yt_vid"
```

### Plan enforcement

Tests that create scheduled posts or connect multiple platforms need team-plan upgrade:

```python
async def test_something_with_scheduling(self, client, authed_user):
    _, _, headers = authed_user
    await _upgrade_team_plan(client, headers, "team")  # Creator tier blocks scheduling
    # ... now scheduling works
```

### Rate-limit cache clearing

Tests that make many rapid requests to rate-limited endpoints need to clear the in-memory cache:

```python
@pytest.fixture(autouse=True)
def _clear_rate_limits():
    from app.common.ratelimit import _local_cache
    _local_cache.clear()
```

## Known gotchas

| Gotcha | Fix |
|---|---|
| `asyncpg` "Future attached to a different loop" | Every fixture that creates `AsyncSessionLocal()` must call `await engine.dispose()` in teardown |
| Stale `scheduled` posts from prior runs pollute worker tests | Clear them in the `db_session` fixture |
| Rate limiter accumulates across tests (shared ASGI transport, no real IP) | `_local_cache.clear()` in autouse fixture or before the test |
| `MSYS_NO_PATHCONV=1` needed on Windows (Git Bash converts `/api/v1` to a Windows path) | Prefix all pytest commands with `MSYS_NO_PATHCONV=1` |
| UNIQUE constraint collisions from hardcoded test IDs (e.g., `sub_test_123`) | Generate unique IDs per test via `uuid.uuid4().hex[:8]` |
| Plan enforcement gates fire before business logic on Creator-tier users | Call `_upgrade_team_plan(client, headers, "team")` in tests that need scheduling/multi-connections |

## Test file map

| File | Tests | What it covers |
|---|---|---|
| `test_health.py` | 2 | `/health` + `/` endpoints |
| `test_auth.py` | 4 | Profile CRUD |
| `test_creators.py` | 12 | Creator tracking CRUD + cross-team |
| `test_videos.py` | 10 | Video tracking CRUD + cross-team |
| `test_niches.py` | 12 | Niche CRUD + feed |
| `test_discover_search.py` | 8 | Public search + platform filtering |
| `test_outlier.py` | 5 | Z-score outlier detection |
| `test_ai.py` | 8 | AI content brief (mock + Claude mock) |
| `test_oauth.py` | 10 | Full OAuth flow (authorize → callback → list → delete) |
| `test_analytics.py` | 10 | Overview, timelines, niche perf, recent outliers |
| `test_cache.py` | 6 | TTL cache helper (Upstash + in-memory) |
| `test_encryption.py` | 4 | Fernet encrypt/decrypt round-trip |
| `test_pagination.py` | 5 | Cursor pagination |
| `test_mock_provider.py` | 6 | MockDataProvider determinism |
| `test_router.py` | 4 | DataProviderRouter dispatch |
| `test_workers.py` | 8 | QStash workers (scrape, discover) |
| `test_storage.py` | 18 | Storage backends + factory |
| `test_publishing_presign.py` | 9 | Presign endpoint |
| `test_scheduled_posts.py` | 22 | ScheduledPost CRUD + cross-team |
| `test_publisher_mock.py` | 3 | MockPublisher |
| `test_publisher_youtube.py` | 7 | YouTube publisher (httpx mocked) |
| `test_publisher_instagram.py` | 7 | Instagram publisher (httpx mocked) |
| `test_publisher_factory.py` | 7 | Publisher factory (real vs mock gating) |
| `test_publish_worker.py` | 8 | Publish worker (SKIP LOCKED, failure paths) |
| `test_plan_limits.py` | 11 | PLAN_LIMITS config validation |
| `test_stripe_mock.py` | 9 | MockStripeClient + factory |
| `test_team_trial.py` | 6 | TeamResponse trial flags + /teams/me |
| `test_billing_routes.py` | 7 | Checkout + portal endpoints |
| `test_billing_webhook.py` | 6 | Webhook dispatch (checkout, update, cancel, reactivation) |
| `test_enforcement.py` | 16 | Plan enforcement (limits, cancelled, trial-expired, cross-team) |
| **Total** | **299** | |
