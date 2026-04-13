"""Tests for app.common.cache."""

import pytest

from app.common.cache import _local_cache, cached, invalidate


class TestCached:
    async def test_computes_on_miss(self) -> None:
        _local_cache.clear()
        calls = []

        async def compute():
            calls.append(1)
            return {"value": 42}

        result = await cached("test:miss", ttl_seconds=60, compute=compute)
        assert result == {"value": 42}
        assert len(calls) == 1

    async def test_returns_cached_on_hit(self) -> None:
        _local_cache.clear()
        calls = []

        async def compute():
            calls.append(1)
            return {"value": 99}

        # First call: miss → compute
        await cached("test:hit", ttl_seconds=60, compute=compute)
        assert len(calls) == 1

        # Second call: hit → no compute
        result = await cached("test:hit", ttl_seconds=60, compute=compute)
        assert result == {"value": 99}
        assert len(calls) == 1  # still 1

    async def test_different_keys_independent(self) -> None:
        _local_cache.clear()

        async def compute_a():
            return "alpha"

        async def compute_b():
            return "bravo"

        await cached("test:a", ttl_seconds=60, compute=compute_a)
        await cached("test:b", ttl_seconds=60, compute=compute_b)

        a = await cached("test:a", ttl_seconds=60, compute=compute_a)
        b = await cached("test:b", ttl_seconds=60, compute=compute_b)
        assert a == "alpha"
        assert b == "bravo"

    async def test_invalidate_clears_key(self) -> None:
        _local_cache.clear()
        calls = []

        async def compute():
            calls.append(1)
            return "fresh"

        await cached("test:inv", ttl_seconds=60, compute=compute)
        assert len(calls) == 1

        await invalidate("test:inv")

        # Should recompute after invalidation
        result = await cached("test:inv", ttl_seconds=60, compute=compute)
        assert result == "fresh"
        assert len(calls) == 2

    async def test_custom_serializer(self) -> None:
        """Works with non-JSON-native types via custom serialize/deserialize."""
        _local_cache.clear()

        from pydantic import BaseModel

        class Metric(BaseModel):
            count: int

        async def compute():
            return Metric(count=7)

        result = await cached(
            "test:pydantic",
            ttl_seconds=60,
            compute=compute,
            serialize=lambda m: m.model_dump_json(),
            deserialize=lambda s: Metric.model_validate_json(s),
        )
        assert result.count == 7

        # Cache hit with same deserializer
        result2 = await cached(
            "test:pydantic",
            ttl_seconds=60,
            compute=compute,
            serialize=lambda m: m.model_dump_json(),
            deserialize=lambda s: Metric.model_validate_json(s),
        )
        assert result2.count == 7
