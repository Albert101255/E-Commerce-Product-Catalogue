import json
import logging
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.monitoring import JSONFormatter
from app.core.security import get_password_hash
from app.models.user import User, UserRole


async def get_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    email = f"admin_mon_{uuid.uuid4().hex}@example.com"
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
    email = f"customer_mon_{uuid.uuid4().hex}@example.com"
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
async def test_metrics_endpoints_and_accumulation(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin_token = await get_admin_token(client, db)
    customer_token = await get_customer_token(client, db)

    # 1. Fetch metrics initial check
    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "antigravity_http_request_duration_seconds" in metrics_resp.text

    # 2. Add product
    cat = await client.post(
        "/api/v1/category/",
        json={"name": "Gaming", "slug": "gaming"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = await client.post(
        "/api/v1/brand/",
        json={"name": "GameBrand", "slug": "gamebrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod = await client.post(
        "/api/v1/products/",
        json={
            "sku": "SKU-MON1",
            "name": "Gaming Mouse",
            "slug": "gaming-mouse",
            "price": 49.99,
            "category_id": cat.json()["id"],
            "brand_id": brand.json()["id"],
            "variants": [
                {
                    "sku": "SKU-MON1-V1",
                    "name": "RGB Mouse",
                    "price": 49.99,
                    "quantity_in_stock": 10,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant_id = prod.json()["variants"][0]["id"]

    # 3. Add item to cart (increments cart_additions_total)
    await client.post(
        "/api/v1/cart/add",
        json={"product_variant_id": variant_id, "quantity": 1},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    metrics_resp = await client.get("/metrics")
    assert "antigravity_cart_additions_total" in metrics_resp.text

    # 4. Perform checkout (increments orders_total)
    await client.post(
        "/api/v1/orders/",
        json={
            "shipping_address": {"street": "456 Peak Rd", "city": "Boulder"},
            "billing_address": {"street": "456 Peak Rd", "city": "Boulder"},
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    metrics_resp2 = await client.get("/metrics")
    assert "antigravity_orders_total" in metrics_resp2.text
    assert "antigravity_active_sessions" in metrics_resp2.text


def test_json_logging_format() -> None:
    # Setup test handler
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)

    # Simple buffer-based stream handler
    from io import StringIO

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    logger.info("Test metric logs message")

    log_output = stream.getvalue().strip()
    log_dict = json.loads(log_output)

    assert log_dict["level"] == "INFO"
    assert log_dict["message"] == "Test metric logs message"
    assert "timestamp" in log_dict
    assert "filename" in log_dict
    assert "line" in log_dict

    # Test formatting of exceptions
    try:
        raise ValueError("An intentional test error")
    except ValueError:
        logger.error("An error occurred", exc_info=True)

    log_lines = stream.getvalue().strip().split("\n")
    error_dict = json.loads(log_lines[-1])
    assert "exception" in error_dict
    assert "ValueError: An intentional test error" in error_dict["exception"]
