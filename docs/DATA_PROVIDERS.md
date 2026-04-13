# Data Providers

> Pluggable adapter pattern for reading data from external platforms. Mock-first — full stack runs without API keys.

## Architecture

```
DataProviderRouter (registry)
  ├── YouTubeProvider     (YouTube Data API v3)     — or MockDataProvider("youtube")
  ├── NetrowsProvider     (LinkedIn via Netrows)    — or MockDataProvider("linkedin")
  ├── Data365Provider     (TikTok via Data365)      — or MockDataProvider("tiktok")
  └── Data365Provider     (Instagram via Data365)   — or MockDataProvider("instagram")
```

**File layout:**

```
app/platforms/
  base.py      # Platform enum, VideoSearchResult, CreatorProfile, VideoMetrics, DataProvider ABC
  router.py    # DataProviderRouter — multi-platform parallel dispatch
  factory.py   # build_router(settings) — picks real vs mock per platform
  mock.py      # MockDataProvider — deterministic fake data
  youtube.py   # YouTubeProvider — YouTube Data API v3
  netrows.py   # NetrowsProvider — LinkedIn via Netrows API
  data365.py   # Data365Provider — TikTok + Instagram via Data365 API
```

## DataProvider ABC

Every provider implements three methods:

```python
class DataProvider(ABC):
    platform: Platform
    name: str

    async def search_videos(self, query: str, limit: int = 20) -> list[VideoSearchResult]
    async def get_creator(self, platform_id: str) -> CreatorProfile | None
    async def get_video_metrics(self, platform_video_id: str) -> VideoMetrics | None
    async def close(self) -> None  # optional cleanup
```

## Platform enum

```python
class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
```

## Shared schemas

| Schema | Purpose | Key fields |
|---|---|---|
| `VideoSearchResult` | Normalized video from any provider | `platform`, `platform_video_id`, `url`, `title`, `views`, `likes`, `comments`, `shares`, `engagement_rate`, `outlier_score`, `is_outlier` |
| `CreatorProfile` | Normalized creator | `platform`, `platform_id`, `username`, `followers`, `verified` |
| `VideoMetrics` | Snapshot of current metrics | `views`, `likes`, `comments`, `shares`, `engagement_rate`, `fetched_at` |

## DataProviderRouter

Registry that dispatches calls to per-platform adapters.

```python
router = DataProviderRouter()
router.register(YouTubeProvider(api_key="..."))
router.register(MockDataProvider(Platform.LINKEDIN))

# Multi-platform parallel search
results = await router.search_videos("fitness", [Platform.YOUTUBE, Platform.LINKEDIN])
# → {Platform.YOUTUBE: [...], Platform.LINKEDIN: [...]}

# Single-platform creator lookup
profile = await router.get_creator(Platform.YOUTUBE, "UC...")
```

**Key behavior:**
- `search_videos` runs all platforms in parallel via `asyncio.gather`
- Failed providers return empty lists (partial results > total failure)
- Missing providers are skipped with a warning
- `provider_summary` property for health check / startup logs

## Factory

`build_router(settings)` in `factory.py`:

| Platform | Condition | Real provider | Fallback |
|---|---|---|---|
| YouTube | `YOUTUBE_API_KEY` set | `YouTubeProvider` | `MockDataProvider("youtube")` |
| LinkedIn | `NETROWS_API_KEY` set | `NetrowsProvider` | `MockDataProvider("linkedin")` |
| TikTok | `DATA365_API_KEY` set | `Data365Provider("tiktok")` | `MockDataProvider("tiktok")` |
| Instagram | `DATA365_API_KEY` set | `Data365Provider("instagram")` | `MockDataProvider("instagram")` |

## MockDataProvider

Returns deterministic fake data seeded by query/platform_id hash. No network calls.

- `search_videos(query)` → 20 fake videos with titles like `"{query} hack that broke the internet"`
- View counts distributed such that ~2 of 20 results are outliers (Z-score >= 3.0)
- `get_creator(platform_id)` → deterministic fake creator profile
- `get_video_metrics(video_id)` → deterministic metrics

## Real providers

### YouTubeProvider (`youtube.py`)

- Uses `httpx` to call YouTube Data API v3
- `search_videos` → `GET https://www.googleapis.com/youtube/v3/search?type=video&videoDuration=short`
- `get_creator` → `GET .../channels?part=snippet,statistics`
- `get_video_metrics` → `GET .../videos?part=statistics`
- Quota: 10,000 units/day (search = 100 units, video detail = 1 unit)

### NetrowsProvider (`netrows.py`)

- Uses `httpx` to call Netrows API
- LinkedIn video search + creator profiles
- ~$53/mo for 10K credits
- **The LinkedIn differentiator** — no other tool in the market tracks LinkedIn video

### Data365Provider (`data365.py`)

- Uses `httpx` to call Data365 API
- Covers both TikTok and Instagram (same provider, different `platform` param)
- $99/mo
- Video search, creator lookup, metrics

## Adding a new provider

1. Create `app/platforms/newplatform.py`
2. Implement `DataProvider` ABC (3 methods + `platform` + `name`)
3. Add to `factory.py`:
   ```python
   if settings.NEW_PLATFORM_API_KEY:
       router.register(NewPlatformProvider(api_key=settings.NEW_PLATFORM_API_KEY))
   else:
       router.register(MockDataProvider(Platform.NEW))
   ```
4. Add `NEW_PLATFORM_API_KEY: str = ""` to `config.py`
5. Add the mock fallback to `MockDataProvider._mock_scopes()` if it needs OAuth
6. Write tests that mock the HTTP calls with `unittest.mock.patch`

## Outlier detection

Runs on search results in `discovery/outlier.py`:

```python
def calculate_outlier_scores(results: list[VideoSearchResult]) -> list[VideoSearchResult]:
    # For each video:
    # 1. baseline = median views across all results
    # 2. std_dev = standard deviation of views
    # 3. outlier_score = (video_views - baseline) / std_dev  (Z-score)
    # 4. is_outlier = outlier_score >= 3.0
```

Applied per-platform within each niche search. Videos with `outlier_score >= 3.0` get the outlier badge in the UI and the "Generate idea" + "Schedule a response" buttons.

## Usage in the codebase

| Consumer | What it calls |
|---|---|
| `POST /discover/search` | `router.search_videos(query, platforms)` |
| `POST /creators/track` | `router.get_creator(platform, platform_id)` |
| `POST /workers/scrape-creators` | `router.get_creator(platform, platform_id)` per tracked creator |
| `POST /workers/scrape-videos` | `router.get_video_metrics(platform, video_id)` per tracked video |
| `POST /workers/discover-trends` | `router.search_videos(query, platforms)` per active niche |
