"""Z-score outlier detection — the "magic" Virlo charges credits for.

Given a list of videos in a niche/search context, flag the ones whose view
counts are statistically significant outliers (default: ≥3 standard deviations
above the mean). These are videos performing 10x+ above their peers — exactly
what creators want to spot before saturation.

This is the same algorithm as Virlo's "Outlier Analysis", but ours runs on
every search, unlimited, with no credit cost.
"""

import math
from typing import Iterable

from app.platforms.base import VideoSearchResult


def calculate_outlier_scores(
    videos: list[VideoSearchResult],
    threshold: float = 3.0,
    metric: str = "views",
) -> list[VideoSearchResult]:
    """Annotate videos with `outlier_score` and `is_outlier` flags.

    Uses the standard Z-score formula: (value - mean) / stdev. A score of 3.0
    means the video is 3 standard deviations above the mean — extremely rare in
    a normal distribution (~0.13% of values). For view counts (which follow a
    log-normal distribution), Z=3 is a very strong outlier signal.

    Args:
        videos: List of VideoSearchResult to score (mutated in place + returned)
        threshold: Z-score threshold above which a video is flagged as outlier
        metric: Which metric to score on — "views", "likes", or "engagement_rate"

    Returns:
        The same list, with `outlier_score` and `is_outlier` populated.
    """
    if len(videos) < 3:
        # Not enough data to compute meaningful statistics
        for v in videos:
            v.outlier_score = None
            v.is_outlier = False
        return videos

    values = [_get_metric(v, metric) for v in videos]
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    stdev = math.sqrt(variance)

    if stdev == 0:
        # All videos identical — no outliers possible
        for v in videos:
            v.outlier_score = 0.0
            v.is_outlier = False
        return videos

    for video, value in zip(videos, values):
        score = (value - mean) / stdev
        video.outlier_score = round(score, 3)
        video.is_outlier = score >= threshold

    return videos


def _get_metric(video: VideoSearchResult, metric: str) -> float:
    if metric == "views":
        return float(video.views)
    if metric == "likes":
        return float(video.likes)
    if metric == "engagement_rate":
        return float(video.engagement_rate or 0)
    raise ValueError(f"Unknown metric: {metric}")


def filter_outliers(videos: Iterable[VideoSearchResult]) -> list[VideoSearchResult]:
    """Return only the videos flagged as outliers."""
    return [v for v in videos if v.is_outlier]
