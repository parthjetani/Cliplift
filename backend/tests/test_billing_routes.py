"""Tests for billing routes — checkout + portal endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.test_creators import _create_real_user, authed_user  # noqa: F401


class TestCheckoutAuth:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"plan": "team", "billing_period": "monthly"},
        )
        assert response.status_code == 401


class TestCheckoutEndpoint:
    async def test_returns_checkout_url(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"plan": "team", "billing_period": "monthly"},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "checkout_url" in body
        assert "session_id" in body
        assert body["checkout_url"].startswith("https://mock.local/checkout/")

    async def test_validates_plan(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"plan": "invalid_plan"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_validates_billing_period(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"plan": "team", "billing_period": "weekly"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_accepts_annual_period(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/billing/checkout",
            json={"plan": "agency", "billing_period": "annual"},
            headers=headers,
        )
        assert response.status_code == 200
        assert "checkout_url" in response.json()


class TestPortalAuth:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/billing/portal")
        assert response.status_code == 401


class TestPortalEndpoint:
    async def test_errors_without_customer(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Fresh team has no stripe_customer_id → portal returns 400."""
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/billing/portal", headers=headers
        )
        assert response.status_code == 400
        assert "No billing account" in response.json()["error"]["message"]
