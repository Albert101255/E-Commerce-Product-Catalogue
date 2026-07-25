import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.product import Product
from app.models.user import User, UserRole


async def get_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"admin_{uuid.uuid4().hex}@example.com"
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


async def get_customer_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"customer_{uuid.uuid4().hex}@example.com"
    customer = User(
        email=email,
        hashed_password=get_password_hash("custpassword"),
        role=UserRole.CUSTOMER,
    )
    db.add(customer)
    await db.flush()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "custpassword"},
    )
    return str(login_response.json()["access_token"])


@pytest.mark.asyncio
async def test_category_crud(client: AsyncClient, db: AsyncSession) -> None:
    admin_token = await get_admin_token(client, db)

    # 1. Create Category (Admin)
    response = await client.post(
        "/api/v1/category/",
        json={"name": "Electronics", "slug": "electronics"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    category_id = response.json()["id"]

    # 2. Get Categories
    get_response = await client.get("/api/v1/category/")
    assert get_response.status_code == 200
    assert len(get_response.json()) >= 1

    # 3. Get Category by slug
    slug_response = await client.get("/api/v1/category/electronics")
    assert slug_response.status_code == 200
    assert slug_response.json()["id"] == category_id


@pytest.mark.asyncio
async def test_product_crud_and_rbac(client: AsyncClient, db: AsyncSession) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # Setup category and brand
    cat_resp = await client.post(
        "/api/v1/category/",
        json={"name": "Clothing", "slug": "clothing"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    category_id = cat_resp.json()["id"]

    brand_resp = await client.post(
        "/api/v1/brand/",
        json={"name": "BrandX", "slug": "brandx"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand_id = brand_resp.json()["id"]

    # 1. Customer attempts to create product -> 403
    p_data = {
        "sku": "PROD-101",
        "name": "Super Shirt",
        "slug": "super-shirt",
        "price": 29.99,
        "category_id": category_id,
        "brand_id": brand_id,
        "variants": [
            {
                "sku": "PROD-101-M",
                "name": "Medium Shirt",
                "price": 29.99,
                "attributes": {"size": "M"},
            }
        ],
    }
    customer_resp = await client.post(
        "/api/v1/products/",
        json=p_data,
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert customer_resp.status_code == 403

    # 2. Admin creates product -> 201
    admin_resp = await client.post(
        "/api/v1/products/",
        json=p_data,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_resp.status_code == 201
    product_id = admin_resp.json()["id"]

    # 3. List products
    list_resp = await client.get("/api/v1/products/")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1
    assert list_resp.json()[0]["name"] == "Super Shirt"

    # 4. Update Product
    update_resp = await client.put(
        f"/api/v1/products/{product_id}",
        json={"price": 24.99},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["price"] == 24.99

    # 5. Delete Product (Soft delete)
    del_resp = await client.delete(
        f"/api/v1/products/{product_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_resp.status_code == 200

    # Verify product is soft deleted (not visible in public listings)
    list_resp_2 = await client.get("/api/v1/products/")
    assert not any(p["id"] == product_id for p in list_resp_2.json())


@pytest.mark.asyncio
async def test_product_reviews_and_denormalization(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # Setup
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Home", "slug": "home"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "HomeBrand", "slug": "homebrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "PROD-202",
            "name": "Coffee Mug",
            "slug": "coffee-mug",
            "price": 9.99,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    product_id = prod.json()["id"]

    # 1. Create a review (rating = 5)
    rev_resp1 = await client.post(
        f"/api/v1/products/{product_id}/reviews",
        json={"rating": 5, "title": "Great", "content": "Awesome product"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert rev_resp1.status_code == 201

    # Verify denormalized rating is 5.0 and count is 1
    db_result1 = await db.execute(select(Product).where(Product.id == product_id))
    product1 = db_result1.scalar_one()
    assert product1.rating == 5.0
    assert product1.review_count == 1

    # 2. Create another review (rating = 3)
    # We need another user to review
    user2_email = f"user2_{uuid.uuid4().hex}@example.com"
    user2 = User(
        email=user2_email,
        hashed_password=get_password_hash("password123"),
        role=UserRole.CUSTOMER,
    )
    db.add(user2)
    await db.flush()
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": user2_email, "password": "password123"},
    )
    token2 = login2.json()["access_token"]

    rev_resp2 = await client.post(
        f"/api/v1/products/{product_id}/reviews",
        json={"rating": 3, "title": "Okay", "content": "It is fine"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert rev_resp2.status_code == 201

    # Verify denormalized rating is 4.0 ((5+3)/2) and count is 2
    db_result2 = await db.execute(select(Product).where(Product.id == product_id))
    product2 = db_result2.scalar_one()
    assert product2.rating == 4.0
    assert product2.review_count == 2
