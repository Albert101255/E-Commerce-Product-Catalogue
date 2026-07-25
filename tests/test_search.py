import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User, UserRole


async def get_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"admin_search_{uuid.uuid4().hex}@example.com"
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
async def test_search_and_autocomplete_indexing(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)

    # 1. Create Categories
    cat_elec = await client.post(
        "/api/v1/category/",
        json={"name": "Electronics", "slug": "electronics"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat_elec.json()["id"]

    # 2. Create Brand
    brand_lap = await client.post(
        "/api/v1/brand/",
        json={"name": "LapBrand", "slug": "lapbrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand_id = brand_lap.json()["id"]

    # 3. Create Product 1 (Laptop)
    prod_laptop = await client.post(
        "/api/v1/products/",
        json={
            "sku": "SKU-LAP1",
            "name": "Super Gaming Laptop",
            "slug": "super-gaming-laptop",
            "price": 1299.99,
            "category_id": cat_id,
            "brand_id": brand_id,
            "variants": [
                {
                    "sku": "SKU-LAP1-V1",
                    "name": "Laptop 16GB RAM",
                    "price": 1299.99,
                    "quantity_in_stock": 5,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prod_laptop.status_code == 201
    prod1_id = prod_laptop.json()["id"]

    # 4. Create Product 2 (Headphones)
    prod_head = await client.post(
        "/api/v1/products/",
        json={
            "sku": "SKU-HEAD1",
            "name": "Noise Cancelling Headphones",
            "slug": "noise-cancelling-headphones",
            "price": 199.99,
            "category_id": cat_id,
            "brand_id": brand_id,
            "variants": [
                {
                    "sku": "SKU-HEAD1-V1",
                    "name": "Headphones Black",
                    "price": 199.99,
                    "quantity_in_stock": 10,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prod_head.status_code == 201
    prod2_id = prod_head.json()["id"]

    # Manually index the products for search test (since delay tasks are mocked out)
    from app.tasks.celery_tasks import async_update_product_search_index_async

    await async_update_product_search_index_async(prod1_id)
    await async_update_product_search_index_async(prod2_id)

    # 5. Search for "laptop"
    search_resp = await client.get("/api/v1/search/?q=laptop")
    assert search_resp.status_code == 200
    data = search_resp.json()
    assert data["total"] == 1
    assert data["results"][0]["name"] == "Super Gaming Laptop"
    assert data["facets"]["categories"]["Electronics"] == 1

    # 6. Autocomplete matching
    auto_resp = await client.get("/api/v1/search/autocomplete?q=Super")
    assert auto_resp.status_code == 200
    assert "Super Gaming Laptop" in auto_resp.json()

    # 7. Update product details and search again
    update_resp = await client.put(
        f"/api/v1/products/{prod1_id}",
        json={"name": "Super Gaming Notebook"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update_resp.status_code == 200

    # Manually index the updated product
    await async_update_product_search_index_async(prod1_id)

    # Search for "Notebook"
    search_updated = await client.get("/api/v1/search/?q=notebook")
    assert search_updated.json()["total"] == 1
    assert search_updated.json()["results"][0]["name"] == "Super Gaming Notebook"

    # 8. Soft Delete product, verify it is removed from index
    delete_resp = await client.delete(
        f"/api/v1/products/{prod1_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delete_resp.status_code == 200

    # Manually index the deleted product (updates soft delete status in search index)
    await async_update_product_search_index_async(prod1_id)

    # Search for "Notebook" should now return 0 results
    search_deleted = await client.get("/api/v1/search/?q=notebook")
    assert search_deleted.json()["total"] == 0
