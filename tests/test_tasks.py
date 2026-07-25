import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.cart import Cart, CartItem
from app.models.user import User, UserRole
from app.tasks.celery_tasks import (
    expire_abandoned_carts_async,
    generate_monthly_sales_report_async,
    send_order_confirmation_email_async,
)


async def get_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"admin_task_{uuid.uuid4().hex}@example.com"
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
    email = f"customer_task_{uuid.uuid4().hex}@example.com"
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
async def test_order_email_and_report_tasks(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # 1. Create product
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Outdoors", "slug": "outdoors"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "CampBrand", "slug": "campbrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "SKU-TENT",
            "name": "Camping Tent",
            "slug": "camping-tent",
            "price": 199.99,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
            "variants": [
                {
                    "sku": "SKU-TENT-V1",
                    "name": "4-Person Tent",
                    "price": 199.99,
                    "quantity_in_stock": 5,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant_id = prod.json()["variants"][0]["id"]

    # 2. Add to cart & Checkout
    await client.post(
        "/api/v1/cart/add",
        json={"product_variant_id": variant_id, "quantity": 1},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    checkout_resp = await client.post(
        "/api/v1/orders/",
        json={
            "shipping_address": {"street": "123 Forest Rd", "city": "Denver"},
            "billing_address": {"street": "123 Forest Rd", "city": "Denver"},
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id = checkout_resp.json()["id"]

    email_result = await send_order_confirmation_email_async(order_id)
    assert "Email sent successfully to" in email_result

    # 3. Generate Monthly Report task
    now = datetime.now(UTC)
    report = await generate_monthly_sales_report_async(now.year, now.month)
    assert report["year"] == now.year
    assert report["month"] == now.month
    assert report["order_count"] >= 1
    assert report["total_sales"] > 0


@pytest.mark.asyncio
async def test_expire_abandoned_carts_task(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)

    # 1. Setup category, brand, and product
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "ToysTask", "slug": "toystask"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "ToyBrandTask", "slug": "toybrandtask"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "SKU-TOYTASK",
            "name": "Toy Task Car",
            "slug": "toy-task-car",
            "price": 15.00,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
            "variants": [
                {
                    "sku": "SKU-TOYTASK-V1",
                    "name": "Red Task Car",
                    "price": 15.00,
                    "quantity_in_stock": 20,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant_id = prod.json()["variants"][0]["id"]

    # 2. Find/create user
    email = f"user_cart_{uuid.uuid4().hex}@example.com"
    user = User(
        email=email,
        hashed_password=get_password_hash("password"),
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    await db.flush()

    # 3. Create an already expired cart
    expired_time = datetime.now(UTC) - timedelta(days=8)
    cart = Cart(user_id=user.id, expires_at=expired_time)
    db.add(cart)
    await db.flush()

    # Add item to expired cart
    cart_item = CartItem(
        cart_id=cart.id,
        product_variant_id=variant_id,
        quantity=1,
        price_at_add=15.0,
    )
    db.add(cart_item)
    await db.flush()

    # Verify cart and item exist
    c_stmt = select(Cart).where(Cart.id == cart.id)
    c_res = await db.execute(c_stmt)
    assert c_res.scalar_one_or_none() is not None

    # 4. Run background cart expiration task
    task_res = await expire_abandoned_carts_async()
    assert "Expired 1 abandoned carts" in task_res

    # 5. Verify cart and its items are deleted
    c_res2 = await db.execute(c_stmt)
    assert c_res2.scalar_one_or_none() is None
