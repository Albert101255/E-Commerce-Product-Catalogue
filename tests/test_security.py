import pytest
from httpx import AsyncClient

from app.core.rate_limit import _local_limits


@pytest.mark.asyncio
async def test_security_headers(client: AsyncClient) -> None:
    # Query health check
    resp = await client.get("/health")
    assert resp.status_code == 200

    # Verify Helmet security headers are present
    headers = resp.headers
    assert "Strict-Transport-Security" in headers
    assert "X-Frame-Options" in headers
    assert headers["X-Frame-Options"] == "DENY"
    assert "X-Content-Type-Options" in headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in headers
    assert "Referrer-Policy" in headers


@pytest.mark.asyncio
async def test_cors_headers(client: AsyncClient) -> None:
    # Query endpoint with CORS origin header
    origin = "http://localhost:3000"
    resp = await client.get("/health", headers={"Origin": origin})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


@pytest.mark.asyncio
async def test_rate_limiting_ip(client: AsyncClient) -> None:
    import os

    # Enable rate limiting for this test case
    os.environ["ENABLE_RATE_LIMIT"] = "true"
    try:
        # Clear any previous limits to isolate this test
        _local_limits.clear()

        # The IP rate limit is set to 20 requests per minute
        # Make 20 requests rapidly (all should succeed)
        for _ in range(20):
            resp = await client.get("/health")
            assert resp.status_code == 200

        # The 21st request should be blocked with 429 Too Many Requests
        blocked_resp = await client.get("/health")
        assert blocked_resp.status_code == 429
        assert (
            blocked_resp.json()["detail"] == "Too Many Requests. Rate limit exceeded."
        )
    finally:
        os.environ.pop("ENABLE_RATE_LIMIT", None)
        _local_limits.clear()

    # Clear limits afterward to avoid blocking other tests
    _local_limits.clear()
