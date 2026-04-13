"""Discovery service — orchestrates search across providers + outlier scoring."""

from app.discovery.outlier import calculate_outlier_scores
from app.discovery.schemas import (
    PlatformResultSummary,
    SearchRequest,
    SearchResponse,
)
from app.platforms.router import DataProviderRouter


async def search_videos(
    router: DataProviderRouter,
    request: SearchRequest,
) -> SearchResponse:
    """Run a multi-platform search, score outliers, sort, and package the response.

    Outlier scoring is per-platform (not global) because Z-scores are only
    meaningful within a comparable population. A LinkedIn video with 50k views
    and a TikTok video with 50k views are not statistically equivalent.
    """
    by_platform_results = await router.search_videos(
        query=request.query,
        platforms=request.platforms,
        limit_per_platform=request.limit_per_platform,
    )

    summaries: list[PlatformResultSummary] = []
    all_videos = []

    for platform, videos in by_platform_results.items():
        scored = calculate_outlier_scores(videos, threshold=request.outlier_threshold)
        outlier_count = sum(1 for v in scored if v.is_outlier)
        summaries.append(
            PlatformResultSummary(
                platform=platform,
                count=len(scored),
                outlier_count=outlier_count,
            )
        )
        all_videos.extend(scored)

    # Sort: outliers first, then by views descending
    all_videos.sort(
        key=lambda v: (v.is_outlier, v.views),
        reverse=True,
    )

    return SearchResponse(
        query=request.query,
        total=len(all_videos),
        outlier_count=sum(1 for v in all_videos if v.is_outlier),
        by_platform=summaries,
        videos=all_videos,
    )
