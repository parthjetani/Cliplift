"""Shared FastAPI dependencies.

Re-exports the most commonly used dependencies for convenience:
- `get_db` — async database session
- Pagination params (cursor-based)

Auth dependencies (`get_current_user`, etc.) live in `app.auth.dependencies`
and are imported there to avoid circular imports.
"""

from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal, get_db


class PaginationParams(BaseModel):
    """Cursor-based pagination query parameters.

    Used as a FastAPI dependency on list endpoints:

        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            ...
    """

    limit: int = Field(default=20, ge=1, le=100, description="Max items per page")
    cursor: str | None = Field(
        default=None,
        description="Opaque base64-encoded cursor from a previous response",
    )


def pagination_params(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginationParams:
    """FastAPI dependency factory for pagination params."""
    return PaginationParams(limit=limit, cursor=cursor)


__all__ = [
    "AsyncSessionLocal",
    "PaginationParams",
    "get_db",
    "pagination_params",
]
