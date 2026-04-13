"""Storage backend abstraction — Supabase Storage with local-disk fallback.

Mirrors the mock-first pattern used by `common/cache.py` and `common/ratelimit.py`:
- `SupabaseStorageBackend` activates when `SUPABASE_SERVICE_ROLE_KEY` is set.
- `LocalStorageBackend` writes to `./uploads/` otherwise — covers tests + dev.

Usage flow:
1. Frontend calls `POST /publishing/uploads/presign` → backend asks the storage
   for `create_upload_url(file_key, content_type)`.
2. Browser PUTs the video bytes directly to that URL — bytes never touch FastAPI.
3. Browser calls `POST /publishing/scheduled-posts` with the `file_key`.
4. The publish worker later calls `download_bytes(file_key)` and pushes the
   bytes to YouTube/Instagram.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol every storage backend implements."""

    async def create_upload_url(
        self, file_key: str, content_type: str, expires_in: int = 600
    ) -> str:
        """Return a URL the browser can PUT bytes to."""
        ...

    async def create_download_url(
        self, file_key: str, expires_in: int = 300
    ) -> str:
        """Return a URL anyone can GET to fetch the file."""
        ...

    async def write_bytes(
        self,
        file_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Write bytes directly. Used by tests + the dev local PUT route."""
        ...

    async def download_bytes(self, file_key: str) -> bytes:
        """Read the file bytes. Used by the publish worker."""
        ...

    async def delete(self, file_key: str) -> None:
        """Delete the file. Idempotent — missing files are not an error."""
        ...

    async def exists(self, file_key: str) -> bool:
        """Check whether the file exists."""
        ...


# ----------------------------------------------------------------------------
# Local-disk backend (dev + tests)
# ----------------------------------------------------------------------------


class LocalStorageBackend:
    """Disk-backed storage for dev and tests.

    Writes to `<root_dir>/<file_key>`. The "presigned URL" is a route on this
    same FastAPI server that proxies bytes to/from disk. Used when
    `SUPABASE_SERVICE_ROLE_KEY` is empty.
    """

    def __init__(self, root_dir: Path | str, public_base_url: str) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.public_base_url = public_base_url.rstrip("/")

    def _path(self, file_key: str) -> Path:
        clean = file_key.lstrip("/").replace("\\", "/")
        path = (self.root_dir / clean).resolve()
        # Guard against path traversal: resolved path must stay under root_dir.
        if not str(path).startswith(str(self.root_dir)):
            raise ValueError(f"Invalid file_key (path traversal): {file_key}")
        return path

    async def create_upload_url(
        self, file_key: str, content_type: str, expires_in: int = 600
    ) -> str:
        # Local backend doesn't sign — returns the dev PUT route URL.
        return f"{self.public_base_url}/api/v1/publishing/uploads/local/{file_key}"

    async def create_download_url(
        self, file_key: str, expires_in: int = 300
    ) -> str:
        return f"{self.public_base_url}/api/v1/publishing/uploads/local/{file_key}"

    async def write_bytes(
        self,
        file_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        path = self._path(file_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def download_bytes(self, file_key: str) -> bytes:
        path = self._path(file_key)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {file_key}")
        return path.read_bytes()

    async def delete(self, file_key: str) -> None:
        path = self._path(file_key)
        if path.exists():
            path.unlink()

    async def exists(self, file_key: str) -> bool:
        return self._path(file_key).exists()


# ----------------------------------------------------------------------------
# Supabase Storage backend (production)
# ----------------------------------------------------------------------------


class SupabaseStorageBackend:
    """Supabase Storage via the REST API.

    Uses the service role key for server-side operations (presign, delete,
    download). The signed upload URL it returns can be used by the browser
    without any auth header.

    The httpx client is created once in __init__ and reused across all
    requests (connection pooling). Call close() during app shutdown.
    """

    def __init__(
        self,
        supabase_url: str,
        service_role_key: str,
        bucket: str,
    ) -> None:
        self.base = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.bucket = bucket
        self._client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "apikey": service_role_key,
            },
        )

    async def close(self) -> None:
        """Close the underlying HTTP client. Called from app lifespan shutdown."""
        await self._client.aclose()

    def _absolutize(self, signed_url: str) -> str:
        """Supabase returns relative URLs like `/object/sign/...?token=...`."""
        if signed_url.startswith("http"):
            return signed_url
        if signed_url.startswith("/"):
            return f"{self.base}/storage/v1{signed_url}"
        return f"{self.base}/storage/v1/{signed_url}"

    async def create_upload_url(
        self, file_key: str, content_type: str, expires_in: int = 600
    ) -> str:
        url = f"{self.base}/storage/v1/object/upload/sign/{self.bucket}/{file_key}"
        resp = await self._client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"expiresIn": expires_in},
        )
        resp.raise_for_status()
        data = resp.json()
        signed_url = data.get("url") or data.get("signedUrl") or ""
        return self._absolutize(signed_url)

    async def create_download_url(
        self, file_key: str, expires_in: int = 300
    ) -> str:
        url = f"{self.base}/storage/v1/object/sign/{self.bucket}/{file_key}"
        resp = await self._client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"expiresIn": expires_in},
        )
        resp.raise_for_status()
        data = resp.json()
        signed_url = data.get("signedURL") or data.get("signedUrl") or ""
        return self._absolutize(signed_url)

    async def write_bytes(
        self,
        file_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        url = f"{self.base}/storage/v1/object/{self.bucket}/{file_key}"
        resp = await self._client.post(
            url,
            headers={
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=data,
        )
        resp.raise_for_status()

    async def download_bytes(self, file_key: str) -> bytes:
        url = f"{self.base}/storage/v1/object/{self.bucket}/{file_key}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.content

    async def delete(self, file_key: str) -> None:
        url = f"{self.base}/storage/v1/object/{self.bucket}/{file_key}"
        resp = await self._client.delete(url)
        if resp.status_code not in (200, 204, 404):
            resp.raise_for_status()

    async def exists(self, file_key: str) -> bool:
        url = f"{self.base}/storage/v1/object/info/{self.bucket}/{file_key}"
        resp = await self._client.get(url)
        return resp.status_code == 200


# ----------------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------------


def build_storage(settings: Settings) -> StorageBackend:
    """Pick a storage backend based on `STORAGE_BACKEND` setting.

    - `local`    → `LocalStorageBackend(./uploads)` always.
    - `supabase` → `SupabaseStorageBackend` (requires SUPABASE_SERVICE_ROLE_KEY).
    - `auto`     → `SupabaseStorageBackend` iff `ENVIRONMENT=production` AND
                   `SUPABASE_SERVICE_ROLE_KEY` is set; otherwise `LocalStorageBackend`.

    The "auto" default keeps dev + tests on local disk even when the local
    Supabase stack is running (which sets `SUPABASE_SERVICE_ROLE_KEY` in the
    environment). Production deployments set `ENVIRONMENT=production` and get
    Supabase Storage automatically.
    """
    use_supabase = False
    if settings.STORAGE_BACKEND == "supabase":
        use_supabase = True
    elif settings.STORAGE_BACKEND == "auto":
        use_supabase = bool(
            settings.is_production and settings.SUPABASE_SERVICE_ROLE_KEY
        )

    if use_supabase:
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "STORAGE_BACKEND=supabase requires SUPABASE_SERVICE_ROLE_KEY"
            )
        logger.info(
            f"Storage: Supabase Storage bucket={settings.SUPABASE_STORAGE_BUCKET}"
        )
        return SupabaseStorageBackend(
            supabase_url=settings.SUPABASE_URL,
            service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            bucket=settings.SUPABASE_STORAGE_BUCKET,
        )

    logger.info(f"Storage: local disk at {settings.LOCAL_STORAGE_DIR}")
    return LocalStorageBackend(
        root_dir=settings.LOCAL_STORAGE_DIR,
        public_base_url=settings.LOCAL_STORAGE_PUBLIC_BASE_URL,
    )
