"""Tests for app.common.pagination."""

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from app.common.pagination import (
    PaginatedResponse,
    decode_cursor,
    encode_cursor,
)


class TestCursorEncoding:
    def test_round_trip(self) -> None:
        now = datetime(2026, 4, 8, 12, 30, 45, tzinfo=timezone.utc)
        item_id = uuid4()
        cursor = encode_cursor(now, item_id)
        decoded_at, decoded_id = decode_cursor(cursor)
        assert decoded_at == now
        assert decoded_id == str(item_id)

    def test_cursor_is_url_safe(self) -> None:
        now = datetime.now(timezone.utc)
        cursor = encode_cursor(now, uuid4())
        # URL-safe base64 uses [A-Za-z0-9_-]
        assert all(c.isalnum() or c in "_-" for c in cursor)
        # Padding is stripped
        assert "=" not in cursor

    def test_cursor_is_deterministic(self) -> None:
        now = datetime(2026, 4, 8, tzinfo=timezone.utc)
        item_id = "abc-123"
        assert encode_cursor(now, item_id) == encode_cursor(now, item_id)

    def test_different_inputs_different_cursors(self) -> None:
        now = datetime(2026, 4, 8, tzinfo=timezone.utc)
        a = encode_cursor(now, "id-a")
        b = encode_cursor(now, "id-b")
        assert a != b

    def test_decode_invalid_cursor_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor("not-a-real-cursor!!!")

    def test_decode_truncated_cursor_raises(self) -> None:
        valid = encode_cursor(datetime.now(timezone.utc), uuid4())
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor(valid[:5])

    def test_decode_empty_cursor_raises(self) -> None:
        with pytest.raises(ValueError):
            decode_cursor("")


class TestPaginatedResponse:
    def test_default_values(self) -> None:
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str

        resp = PaginatedResponse[Item](items=[])
        assert resp.items == []
        assert resp.next_cursor is None
        assert resp.has_more is False

    def test_with_items_and_cursor(self) -> None:
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str

        resp = PaginatedResponse[Item](
            items=[Item(name="a"), Item(name="b")],
            next_cursor="abc123",
            has_more=True,
        )
        assert len(resp.items) == 2
        assert resp.next_cursor == "abc123"
        assert resp.has_more is True
