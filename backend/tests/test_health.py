"""Smoke tests for the basic FastAPI app — verifies Chunk 1 is wired correctly."""

from httpx import AsyncClient


async def test_health_endpoint(client: AsyncClient) -> None:
    """Health check should return 200 with status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body
    assert "version" in body


async def test_root_endpoint(client: AsyncClient) -> None:
    """Root should return app metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Cliplift"
    assert body["docs"] == "/docs"


async def test_openapi_docs_available(client: AsyncClient) -> None:
    """OpenAPI schema should be generated."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Cliplift"


async def test_cors_headers_present(client: AsyncClient) -> None:
    """CORS middleware should add Access-Control headers on preflight."""
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in {k.lower() for k in response.headers.keys()}
