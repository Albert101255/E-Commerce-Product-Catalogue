import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.order import Order, OrderStatus
from app.models.payment import Transaction, TransactionStatus
from app.models.product import ProductVariant
from app.models.user import User, UserRole


async def get_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"admin_pay_{uuid.uuid4().hex}@example.com"
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
    email = f"customer_pay_{uuid.uuid4().hex}@example.com"
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
async def test_payment_processing_flow(client: AsyncClient, db: AsyncSession) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # 1. Setup category, brand, product
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Tools", "slug": "tools"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "ToolBrand", "slug": "toolbrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "PROD-SAW",
            "name": "Power Saw",
            "slug": "power-saw",
            "price": 149.99,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
            "variants": [
                {
                    "sku": "PROD-SAW-V1",
                    "name": "Saw 15amp",
                    "price": 149.99,
                    "quantity_in_stock": 5,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant_id = prod.json()["variants"][0]["id"]

    # 2. Add to cart
    await client.post(
        "/api/v1/cart/add",
        json={"product_variant_id": variant_id, "quantity": 1},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    # 3. Checkout
    checkout_resp = await client.post(
        "/api/v1/orders/",
        json={
            "shipping_address": {"street": "123 Oak St", "city": "Seattle"},
            "billing_address": {"street": "123 Oak St", "city": "Seattle"},
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id = checkout_resp.json()["id"]

    # 4. Save Payment Method
    pm_resp = await client.post(
        "/api/v1/payment-methods",
        json={
            "type": "CREDIT_CARD",
            "stripe_payment_method_id": "pm_123",
            "is_default": True,
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert pm_resp.status_code == 201
    pm_id = pm_resp.json()["id"]

    # 5. Process Payment
    pay_resp = await client.post(
        "/api/v1/checkout/process",
        json={"order_id": order_id, "payment_method_id": pm_id},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert pay_resp.status_code == 200
    assert pay_resp.json()["status"] == TransactionStatus.COMPLETED

    # 6. Verify Order is CONFIRMED
    order_stmt = select(Order).where(Order.id == order_id)
    order_res = await db.execute(order_stmt)
    assert order_res.scalar_one().status == OrderStatus.CONFIRMED


@pytest.mark.asyncio
async def test_order_refund_rbac_and_stock_restoration(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # Setup
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Garden", "slug": "garden"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "GardenBrand", "slug": "gardenbrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "PROD-HOSE",
            "name": "Hose Pipe",
            "slug": "hose-pipe",
            "price": 25.00,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
            "variants": [
                {
                    "sku": "PROD-HOSE-V1",
                    "name": "Hose 50ft",
                    "price": 25.00,
                    "quantity_in_stock": 10,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant_id = prod.json()["variants"][0]["id"]

    # Add & Checkout
    await client.post(
        "/api/v1/cart/add",
        json={"product_variant_id": variant_id, "quantity": 2},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    checkout_resp = await client.post(
        "/api/v1/orders/",
        json={
            "shipping_address": {"street": "123 Main St", "city": "Boston"},
            "billing_address": {"street": "123 Main St", "city": "Boston"},
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id = checkout_resp.json()["id"]

    # Stock is now 8
    stmt = select(ProductVariant).where(ProductVariant.id == variant_id)
    res1 = await db.execute(stmt)
    assert res1.scalar_one().quantity_in_stock == 8

    # Process Payment to make it paid (CONFIRMED)
    await client.post(
        "/api/v1/checkout/process",
        json={"order_id": order_id, "stripe_token": "tok_visa"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    # 1. Customer attempts to refund -> 403 Forbidden
    cust_refund = await client.post(
        f"/api/v1/orders/{order_id}/refund",
        json={"amount": 50.00, "reason": "Customer request"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert cust_refund.status_code == 403

    # 2. Admin refunds order -> 201 Created
    admin_refund = await client.post(
        f"/api/v1/orders/{order_id}/refund",
        json={"amount": 50.00, "reason": "Customer request"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_refund.status_code == 201
    assert admin_refund.json()["status"] == "COMPLETED"

    # 3. Verify stock is restored to 10
    res2 = await db.execute(stmt)
    assert res2.scalar_one().quantity_in_stock == 10

    # 4. Verify transaction status is REFUNDED
    tx_stmt = select(Transaction).where(Transaction.order_id == order_id)
    tx_res = await db.execute(tx_stmt)
    assert tx_res.scalar_one().status == TransactionStatus.REFUNDED
