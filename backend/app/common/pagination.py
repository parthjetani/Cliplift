"""Cursor-based pagination utility for list endpoints.

Cursor-based (not offset-based) because:
- Offset pagination breaks when items are inserted/deleted between requests
- Cursors are stable and performant on large tables (uses index range scans)
- Standard for modern APIs (Stripe, GitHub, etc.)

Usage in a route handler:

    from app.common.pagination import paginate, PaginatedResponse
    from app.dependencies import PaginationParams, pagination_params

    @router.get("", response_model=PaginatedResponse[ItemResponse])
    async def list_items(
        team: Team = Depends(get_current_team),
        db: AsyncSession = Depends(get_db),
        pagination: PaginationParams = Depends(pagination_params),
    ):
        query = select(Item).where(Item.team_id == team.id)
        return await paginate(
            db=db,
            query=query,
            model=Item,
            schema=ItemResponse,
            params=pagination,
        )
"""

import base64
import json
import logging
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope for paginated list responses."""

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


# ----------------------------------------------------------------------------
# Cursor encoding (opaque base64 of (created_at, id))
# ----------------------------------------------------------------------------


def encode_cursor(created_at: datetime, item_id: Any) -> str:
    """Encode (created_at, id) tuple into an opaque base64 cursor."""
    payload = {"t": created_at.isoformat(), "i": str(item_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Decode a cursor back into (created_at, id).

    Raises:
        ValueError: If the cursor is malformed or corrupted.
    """
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + padding)
        payload = json.loads(raw)
        return datetime.fromisoformat(payload["t"]), payload["i"]
    except (ValueError, KeyError, TypeError) as e:
        raise ValueError(f"Invalid cursor: {e}") from e


# ----------------------------------------------------------------------------
# paginate() — main entry point
# ----------------------------------------------------------------------------


async def paginate(
    db: AsyncSession,
    query: Select,
    model: type,
    schema: type[T],
    params: Any,
    timestamp_field: str = "created_at",
) -> PaginatedResponse[T]:
    """Apply cursor-based pagination to a SELECT query.

    Args:
        db: Async session
        query: Base SELECT query (will receive .where() and .order_by() applied)
        model: SQLAlchemy ORM model class
        schema: Pydantic schema to serialize each item into
        params: PaginationParams instance with `.limit` and `.cursor`
        timestamp_field: Column name to sort by. Defaults to "created_at".
            For tracking tables (CreatorTracking, VideoTracking) that use
            "tracked_at" instead, pass that name.

    Returns:
        PaginatedResponse with items, next_cursor, and has_more flag

    Raises:
        ValueError: If the cursor is malformed.
        AttributeError: If the model has no `id` or the requested timestamp column.
    """
    timestamp_col = getattr(model, timestamp_field)
    id_col = model.id

    # Apply cursor filter (keyset pagination — uses tuple comparison)
    if params.cursor:
        cursor_ts, cursor_id = decode_cursor(params.cursor)
        # (timestamp, id) < (cursor_ts, cursor_id) — descending
        query = query.where(
            or_(
                timestamp_col < cursor_ts,
                and_(timestamp_col == cursor_ts, id_col < cursor_id),
            )
        )

    # Always order by (timestamp DESC, id DESC) for stable pagination
    query = query.order_by(timestamp_col.desc(), id_col.desc())

    # Fetch limit + 1 to determine has_more without an extra query
    query = query.limit(params.limit + 1)
    result = await db.execute(query)
    rows = list(result.scalars().unique().all())

    has_more = len(rows) > params.limit
    items = rows[: params.limit]

    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(getattr(last, timestamp_field), last.id)

    return PaginatedResponse[T](
        items=[schema.model_validate(item, from_attributes=True) for item in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )
