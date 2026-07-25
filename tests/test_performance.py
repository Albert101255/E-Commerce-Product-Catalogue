import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import _local_cache
from app.core.security import get_password_hash
from app.models.user import User, UserRole


async def get_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"admin_perf_{uuid.uuid4().hex}@example.com"
    admin = User(
        email=email,
        hashed_password=get_password_hash("adminpassword"),
        role=UserRole.ADMIN,
    )
    db.add(admin)
    await db.flush()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "adminpassword"},
    )
    return str(login_response.json()["access_token"])


@pytest.mark.asyncio
async def test_database_connection_pool_properties(db: AsyncSession) -> None:
    # Verify database engine pool properties
    engine = db.bind
    assert engine is not None
    pool = getattr(engine, "pool", None)
    assert pool is not None
    assert getattr(pool, "_pre_ping", None) is True


@pytest.mark.asyncio
async def test_http_caching_and_etags(client: AsyncClient, db: AsyncSession) -> None:
    admin_token = await get_admin_token(client, db)

    # Clear cache to start fresh
    _local_cache.clear()

    # 1. Setup category, brand, and product
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "OutdoorsPerf", "slug": "outdoorsperf"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "CampPerf", "slug": "campperf"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "SKU-PERF-MOUSE",
            "name": "Perf Mouse",
            "slug": "perf-mouse",
            "price": 29.99,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
            "variants": [
                {
                    "sku": "SKU-PERF-MOUSE-V1",
                    "name": "Red Mouse",
                    "price": 29.99,
                    "quantity_in_stock": 5,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod_id = prod.json()["id"]

    # Clear cache since creation invalidates it
    _local_cache.clear()

    # 2. Query product detail to populate cache and get ETag
    resp1 = await client.get(f"/api/v1/products/{prod_id}")
    assert resp1.status_code == 200
    assert "ETag" in resp1.headers
    assert "Cache-Control" in resp1.headers
    etag = resp1.headers["ETag"]

    # 3. Query again with If-None-Match -> should return 304 Not Modified!
    resp2 = await client.get(
        f"/api/v1/products/{prod_id}", headers={"If-None-Match": etag}
    )
    assert resp2.status_code == 304
    assert resp2.text == ""  # Empty body for 304 responses
