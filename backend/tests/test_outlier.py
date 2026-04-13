"""Unit tests for Z-score outlier detection."""

from datetime import datetime, timezone

import pytest

from app.discovery.outlier import calculate_outlier_scores, filter_outliers
from app.platforms.base import Platform, VideoSearchResult


def make_video(views: int, video_id: str = "test") -> VideoSearchResult:
    return VideoSearchResult(
        platform=Platform.YOUTUBE,
        platform_video_id=video_id,
        url=f"https://youtube.com/{video_id}",
        title=f"Test {video_id}",
        creator_username="test_creator",
        views=views,
    )


class TestOutlierDetection:
    def test_empty_list_returns_empty(self) -> None:
        assert calculate_outlier_scores([]) == []

    def test_too_few_videos_no_score(self) -> None:
        """With <3 videos, scoring is meaningless — no outliers flagged."""
        videos = [make_video(100), make_video(200)]
        result = calculate_outlier_scores(videos)
        assert all(v.outlier_score is None for v in result)
        assert all(v.is_outlier is False for v in result)

    def test_uniform_distribution_no_outliers(self) -> None:
        """If all videos have identical views, none are outliers."""
        videos = [make_video(1000) for _ in range(10)]
        result = calculate_outlier_scores(videos)
        assert all(v.outlier_score == 0.0 for v in result)
        assert all(v.is_outlier is False for v in result)

    def test_obvious_outlier_detected(self) -> None:
        """A video with 100x the median views should be an obvious outlier."""
        baseline = [make_video(1000) for _ in range(20)]
        outlier = make_video(100_000, video_id="OUTLIER")
        videos = baseline + [outlier]
        result = calculate_outlier_scores(videos, threshold=3.0)

        outliers = filter_outliers(result)
        assert len(outliers) == 1
        assert outliers[0].platform_video_id == "OUTLIER"
        assert outliers[0].outlier_score is not None
        assert outliers[0].outlier_score > 3.0

    def test_threshold_respected(self) -> None:
        """A more lenient threshold flags more videos as outliers."""
        videos = [make_video(v) for v in [100, 100, 100, 100, 100, 200, 500]]
        strict = calculate_outlier_scores([make_video(v) for v in [100, 100, 100, 100, 100, 200, 500]], threshold=3.0)
        lenient = calculate_outlier_scores([make_video(v) for v in [100, 100, 100, 100, 100, 200, 500]], threshold=1.5)

        assert len(filter_outliers(lenient)) >= len(filter_outliers(strict))

    def test_score_signed_correctly(self) -> None:
        """Above-average videos have positive scores, below-average have negative."""
        videos = [make_video(v) for v in [100, 100, 100, 1000]]
        result = calculate_outlier_scores(videos)
        # The 1000-view video should have positive score
        assert result[3].outlier_score > 0
        # The 100-view videos should have negative score
        assert result[0].outlier_score < 0
