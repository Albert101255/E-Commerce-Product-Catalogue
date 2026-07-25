import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import _local_cache
from app.core.security import get_password_hash
from app.models.product import Product
from app.models.user import User, UserRole


async def get_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"admin_cache_{uuid.uuid4().hex}@example.com"
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
async def test_cache_hits_and_invalidation(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)

    # Clear any previous local cache
    _local_cache.clear()

    # 1. Setup category, brand, and product
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Toys", "slug": "toys"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "ToyBrand", "slug": "toybrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand_id = brand.json()["id"]

    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "SKU-TOY1",
            "name": "Toy Car",
            "slug": "toy-car",
            "price": 9.99,
            "category_id": cat_id,
            "brand_id": brand_id,
            "variants": [
                {
                    "sku": "SKU-TOY1-V1",
                    "name": "Red Car",
                    "price": 9.99,
                    "quantity_in_stock": 20,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod_id = prod.json()["id"]

    # Clear cache since creation invalidates it
    _local_cache.clear()

    # 2. Query product details (populates cache)
    resp1 = await client.get(f"/api/v1/products/{prod_id}")
    assert resp1.status_code == 200
    assert resp1.json()["name"] == "Toy Car"

    # Confirm key is in _local_cache
    cache_keys = [k for k in _local_cache.keys() if "products:detail" in k]
    assert len(cache_keys) > 0

    # 3. Modify product directly in DB (bypassing endpoints)
    stmt = select(Product).where(Product.id == prod_id)
    res = await db.execute(stmt)
    db_prod = res.scalar_one()
    db_prod.name = "Modified Car Name Direct DB"
    db.add(db_prod)
    await db.flush()

    # 4. Query product details again -> should still return cached old name
    resp2 = await client.get(f"/api/v1/products/{prod_id}")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Toy Car"  # cache hit!

    # 5. Update product using PUT endpoint -> invalidates cache
    update_resp = await client.put(
        f"/api/v1/products/{prod_id}",
        json={"name": "Toy Car V2"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update_resp.status_code == 200

    # 6. Query product details -> should return the updated V2 name
    resp3 = await client.get(f"/api/v1/products/{prod_id}")
    assert resp3.status_code == 200
    assert resp3.json()["name"] == "Toy Car V2"
