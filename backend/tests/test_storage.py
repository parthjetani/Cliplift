"""Tests for storage backends — LocalStorageBackend + SupabaseStorageBackend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.common.storage import (
    LocalStorageBackend,
    SupabaseStorageBackend,
    build_storage,
)
from app.config import Settings


# ============================================================================
# LocalStorageBackend
# ============================================================================


class TestLocalStorageBackend:
    @pytest.fixture
    def backend(self, tmp_path: Path) -> LocalStorageBackend:
        return LocalStorageBackend(
            root_dir=tmp_path,
            public_base_url="http://localhost:8000",
        )

    async def test_round_trip(self, backend: LocalStorageBackend) -> None:
        await backend.write_bytes("team-a/abc/test.mp4", b"hello video")
        assert await backend.exists("team-a/abc/test.mp4")
        data = await backend.download_bytes("team-a/abc/test.mp4")
        assert data == b"hello video"

    async def test_delete_removes_file(self, backend: LocalStorageBackend) -> None:
        await backend.write_bytes("team-a/x/file.mp4", b"x")
        assert await backend.exists("team-a/x/file.mp4")
        await backend.delete("team-a/x/file.mp4")
        assert not await backend.exists("team-a/x/file.mp4")

    async def test_delete_missing_is_idempotent(
        self, backend: LocalStorageBackend
    ) -> None:
        # Should not raise
        await backend.delete("does-not-exist.mp4")

    async def test_download_missing_raises(
        self, backend: LocalStorageBackend
    ) -> None:
        with pytest.raises(FileNotFoundError):
            await backend.download_bytes("missing.mp4")

    async def test_create_upload_url_uses_local_route(
        self, backend: LocalStorageBackend
    ) -> None:
        url = await backend.create_upload_url("team-a/x/file.mp4", "video/mp4")
        assert url == (
            "http://localhost:8000/api/v1/publishing/uploads/local/team-a/x/file.mp4"
        )

    async def test_create_download_url_returns_url(
        self, backend: LocalStorageBackend
    ) -> None:
        url = await backend.create_download_url("team-a/x/file.mp4")
        assert "team-a/x/file.mp4" in url
        assert url.startswith("http://localhost:8000")

    async def test_path_traversal_blocked(
        self, backend: LocalStorageBackend
    ) -> None:
        with pytest.raises(ValueError):
            await backend.write_bytes("../../etc/passwd", b"hack")

    async def test_nested_directories_created(
        self, backend: LocalStorageBackend, tmp_path: Path
    ) -> None:
        await backend.write_bytes("a/b/c/d/file.mp4", b"deep")
        assert (tmp_path / "a" / "b" / "c" / "d" / "file.mp4").exists()


# ============================================================================
# SupabaseStorageBackend (httpx mocked)
# ============================================================================


def _mock_response(json_response: dict, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.json = MagicMock(return_value=json_response)
    resp.raise_for_status = MagicMock()
    resp.status_code = status_code
    resp.content = b""
    return resp


class TestSupabaseStorageBackend:
    @pytest.fixture
    def backend(self) -> SupabaseStorageBackend:
        b = SupabaseStorageBackend(
            supabase_url="https://test.supabase.co",
            service_role_key="test-service-role-key",
            bucket="cliplift-videos",
        )
        # Replace the real httpx client with a mock so no network calls happen
        b._client = AsyncMock()
        return b

    async def test_create_upload_url_calls_storage_api(
        self, backend: SupabaseStorageBackend
    ) -> None:
        backend._client.post = AsyncMock(
            return_value=_mock_response(
                {"url": "/object/upload/sign/cliplift-videos/key?token=tok123"}
            )
        )
        url = await backend.create_upload_url("team-1/x/file.mp4", "video/mp4")

        assert "test.supabase.co" in url
        assert "token=tok123" in url
        assert backend._client.post.call_count == 1
        called_url = backend._client.post.call_args[0][0]
        assert "upload/sign/cliplift-videos/team-1/x/file.mp4" in called_url

    async def test_create_download_url_calls_sign_endpoint(
        self, backend: SupabaseStorageBackend
    ) -> None:
        backend._client.post = AsyncMock(
            return_value=_mock_response(
                {"signedURL": "/object/sign/cliplift-videos/key?token=dl"}
            )
        )
        url = await backend.create_download_url("team-1/x/file.mp4")

        assert "test.supabase.co" in url
        assert "token=dl" in url
        called_url = backend._client.post.call_args[0][0]
        assert "/object/sign/cliplift-videos/team-1/x/file.mp4" in called_url

    async def test_download_bytes_returns_response_content(
        self, backend: SupabaseStorageBackend
    ) -> None:
        mock_resp = _mock_response({})
        mock_resp.content = b"video bytes"
        backend._client.get = AsyncMock(return_value=mock_resp)

        data = await backend.download_bytes("team-1/x/file.mp4")

        assert data == b"video bytes"
        called_url = backend._client.get.call_args[0][0]
        assert "team-1/x/file.mp4" in called_url

    async def test_delete_swallows_404(
        self, backend: SupabaseStorageBackend
    ) -> None:
        mock_resp = _mock_response({}, status_code=404)
        backend._client.delete = AsyncMock(return_value=mock_resp)
        await backend.delete("missing.mp4")  # should not raise


# ============================================================================
# build_storage factory
# ============================================================================


class TestBuildStorageFactory:
    def test_local_in_dev_even_with_service_key(self, tmp_path: Path) -> None:
        """Auto mode in development always picks local, even if SUPABASE_SERVICE_ROLE_KEY
        is set (which it is when local Supabase is running)."""
        s = Settings(
            ENVIRONMENT="development",
            STORAGE_BACKEND="auto",
            SUPABASE_SERVICE_ROLE_KEY="test-key",
            LOCAL_STORAGE_DIR=str(tmp_path),
        )
        backend = build_storage(s)
        assert isinstance(backend, LocalStorageBackend)

    def test_supabase_in_production_with_service_key(self) -> None:
        """Auto mode in production uses Supabase when the service key is set."""
        s = Settings(
            ENVIRONMENT="production",
            STORAGE_BACKEND="auto",
            SUPABASE_SERVICE_ROLE_KEY="prod-key",
            SUPABASE_URL="https://prod.supabase.co",
        )
        backend = build_storage(s)
        assert isinstance(backend, SupabaseStorageBackend)
        assert backend.bucket == "cliplift-videos"

    def test_local_in_production_when_no_service_key(self, tmp_path: Path) -> None:
        """Even in production, falls back to local if no service key is provided."""
        s = Settings(
            ENVIRONMENT="production",
            STORAGE_BACKEND="auto",
            SUPABASE_SERVICE_ROLE_KEY="",
            LOCAL_STORAGE_DIR=str(tmp_path),
        )
        backend = build_storage(s)
        assert isinstance(backend, LocalStorageBackend)

    def test_explicit_supabase_override(self) -> None:
        """STORAGE_BACKEND=supabase forces Supabase even in dev."""
        s = Settings(
            ENVIRONMENT="development",
            STORAGE_BACKEND="supabase",
            SUPABASE_SERVICE_ROLE_KEY="test-key",
        )
        backend = build_storage(s)
        assert isinstance(backend, SupabaseStorageBackend)

    def test_explicit_supabase_without_key_raises(self) -> None:
        """STORAGE_BACKEND=supabase but no service key → loud failure."""
        s = Settings(
            STORAGE_BACKEND="supabase",
            SUPABASE_SERVICE_ROLE_KEY="",
        )
        with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
            build_storage(s)

    def test_explicit_local_override(self, tmp_path: Path) -> None:
        """STORAGE_BACKEND=local forces local even in production with key."""
        s = Settings(
            ENVIRONMENT="production",
            STORAGE_BACKEND="local",
            SUPABASE_SERVICE_ROLE_KEY="prod-key",
            LOCAL_STORAGE_DIR=str(tmp_path),
        )
        backend = build_storage(s)
        assert isinstance(backend, LocalStorageBackend)
