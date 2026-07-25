import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.order import OrderStatus, ReturnStatus
from app.models.product import ProductVariant
from app.models.user import User, UserRole


async def get_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"admin_order_{uuid.uuid4().hex}@example.com"
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
    email = f"customer_order_{uuid.uuid4().hex}@example.com"
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
async def test_shopping_cart_and_checkout_flow(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # 1. Setup category, brand, and product with stock
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Gaming", "slug": "gaming"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    category_id = cat.json()["id"]

    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "BrandY", "slug": "brandy"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand_id = brand.json()["id"]

    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "PROD-GAME",
            "name": "Game Console",
            "slug": "game-console",
            "price": 499.99,
            "category_id": category_id,
            "brand_id": brand_id,
            "variants": [
                {
                    "sku": "PROD-GAME-V1",
                    "name": "Console Black",
                    "price": 499.99,
                    "quantity_in_stock": 10,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant_id = prod.json()["variants"][0]["id"]

    # 2. View empty cart
    cart_resp = await client.get(
        "/api/v1/cart/",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert cart_resp.status_code == 200
    assert len(cart_resp.json()["items"]) == 0

    # 3. Add item to cart
    add_resp = await client.post(
        "/api/v1/cart/add",
        json={"product_variant_id": variant_id, "quantity": 2},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert add_resp.status_code == 201
    assert add_resp.json()["quantity"] == 2
    assert add_resp.json()["price_at_add"] == 499.99

    # 4. View cart with items
    cart_resp = await client.get(
        "/api/v1/cart/",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert len(cart_resp.json()["items"]) == 1

    # 5. Checkout (Create order)
    checkout_resp = await client.post(
        "/api/v1/orders/",
        json={
            "shipping_address": {
                "street": "123 Main St",
                "city": "Boston",
                "state": "MA",
                "zip": "02108",
            },
            "billing_address": {
                "street": "123 Main St",
                "city": "Boston",
                "state": "MA",
                "zip": "02108",
            },
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert checkout_resp.status_code == 201
    order_data = checkout_resp.json()
    assert order_data["status"] == OrderStatus.PENDING
    assert order_data["subtotal"] == 999.98
    assert order_data["total"] > 999.98  # inclusive of tax

    # 6. Verify cart is cleared
    cart_cleared = await client.get(
        "/api/v1/cart/",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert len(cart_cleared.json()["items"]) == 0

    # 7. Verify stock is decremented (10 - 2 = 8)
    stmt = select(ProductVariant).where(ProductVariant.id == variant_id)
    res = await db.execute(stmt)
    variant = res.scalar_one()
    assert variant.quantity_in_stock == 8


@pytest.mark.asyncio
async def test_checkout_insufficient_stock(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # Setup category, brand, and product with 1 stock
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Books", "slug": "books"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "BookBrand", "slug": "bookbrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "PROD-BOOK",
            "name": "Limitless",
            "slug": "limitless",
            "price": 19.99,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
            "variants": [
                {
                    "sku": "PROD-BOOK-V1",
                    "name": "Limitless Hardcover",
                    "price": 19.99,
                    "quantity_in_stock": 1,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant_id = prod.json()["variants"][0]["id"]

    # Add 2 items to cart (more than stock)
    await client.post(
        "/api/v1/cart/add",
        json={"product_variant_id": variant_id, "quantity": 2},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    # Checkout should fail
    checkout_resp = await client.post(
        "/api/v1/orders/",
        json={
            "shipping_address": {"street": "123 Main St", "city": "Boston"},
            "billing_address": {"street": "123 Main St", "city": "Boston"},
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert checkout_resp.status_code == 400
    assert "Insufficient stock" in checkout_resp.json()["detail"]


@pytest.mark.asyncio
async def test_order_cancellation_and_returns(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # Setup
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Kitchen", "slug": "kitchen"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "KitchenBrand", "slug": "kitchenbrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "PROD-PAN",
            "name": "Frying Pan",
            "slug": "frying-pan",
            "price": 39.99,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
            "variants": [
                {
                    "sku": "PROD-PAN-V1",
                    "name": "Pan 10-inch",
                    "price": 39.99,
                    "quantity_in_stock": 5,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant_id = prod.json()["variants"][0]["id"]

    # Add 1 item to cart
    await client.post(
        "/api/v1/cart/add",
        json={"product_variant_id": variant_id, "quantity": 1},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    # Checkout
    checkout_resp = await client.post(
        "/api/v1/orders/",
        json={
            "shipping_address": {"street": "123 Main St", "city": "Boston"},
            "billing_address": {"street": "123 Main St", "city": "Boston"},
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id = checkout_resp.json()["id"]

    # Stock should be 4
    stmt = select(ProductVariant).where(ProductVariant.id == variant_id)
    res = await db.execute(stmt)
    assert res.scalar_one().quantity_in_stock == 4

    # Cancel order (Admin only)
    cancel_resp = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == OrderStatus.CANCELLED

    # Stock should be restored to 5
    res2 = await db.execute(stmt)
    assert res2.scalar_one().quantity_in_stock == 5

    # Re-order
    await client.post(
        "/api/v1/cart/add",
        json={"product_variant_id": variant_id, "quantity": 1},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    checkout_resp2 = await client.post(
        "/api/v1/orders/",
        json={
            "shipping_address": {"street": "123 Main St", "city": "Boston"},
            "billing_address": {"street": "123 Main St", "city": "Boston"},
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id2 = checkout_resp2.json()["id"]
    order_item_id2 = checkout_resp2.json()["items"][0]["id"]

    # Mark as DELIVERED by Admin so we can request return
    status_resp = await client.put(
        f"/api/v1/orders/{order_id2}/status",
        json={"status": OrderStatus.DELIVERED},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_resp.status_code == 200

    # Request Return
    return_resp = await client.post(
        f"/api/v1/orders/{order_id2}/returns",
        json={"order_item_id": order_item_id2, "quantity": 1, "reason": "Defective"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert return_resp.status_code == 201
    assert return_resp.json()["status"] == ReturnStatus.REQUESTED
    assert return_resp.json()["refund_amount"] == 39.99
