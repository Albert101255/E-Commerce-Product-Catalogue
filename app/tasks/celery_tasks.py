import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, func, select

from app.core.celery_app import celery_app
from app.crud.search_indexer import update_product_index
from app.db.base import AsyncSessionLocal
from app.models.cart import Cart, CartItem
from app.models.order import Order
from app.models.user import User


def run_async_task(coro: Any) -> Any:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)


async def send_order_confirmation_email_async(order_id: int) -> str:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return f"Order {order_id} not found"

        user_result = await db.execute(select(User).where(User.id == order.user_id))
        user = user_result.scalar_one_or_none()
        user_email = user.email if user else "unknown@example.com"

        # Print mock log
        print(
            f"[MOCK EMAIL] To: {user_email} | "
            f"Subject: Order Confirmation | "
            f"Body: Thank you for your order {order.order_number}!"
        )
        return f"Email sent successfully to {user_email}"


async def async_update_product_search_index_async(product_id: int) -> str:
    async with AsyncSessionLocal() as db:
        await update_product_index(db, product_id=product_id)
        await db.commit()
        return f"Product {product_id} search index updated successfully"


async def expire_abandoned_carts_async() -> str:
    async with AsyncSessionLocal() as db:
        now = datetime.now(UTC)
        # Find expired carts
        carts_result = await db.execute(select(Cart).where(Cart.expires_at < now))
        expired_carts = carts_result.scalars().all()
        expired_cart_ids = [c.id for c in expired_carts]

        if expired_cart_ids:
            # Clear all items in expired carts
            await db.execute(
                delete(CartItem).where(CartItem.cart_id.in_(expired_cart_ids))
            )
            # Delete the carts
            await db.execute(delete(Cart).where(Cart.id.in_(expired_cart_ids)))
            await db.commit()

        return f"Expired {len(expired_cart_ids)} abandoned carts"


async def generate_monthly_sales_report_async(year: int, month: int) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        # Query all orders in the given year/month
        start_date = datetime(year, month, 1, tzinfo=UTC)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=UTC)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=UTC)

        result = await db.execute(
            select(
                func.coalesce(func.sum(Order.total), 0.0),
                func.count(Order.id),
            )
            .where(Order.created_at >= start_date)
            .where(Order.created_at < end_date)
        )
        total_sales, order_count = result.all()[0]

        report_data = {
            "year": year,
            "month": month,
            "total_sales": float(total_sales),
            "order_count": int(order_count),
            "generated_at": datetime.now(UTC).isoformat(),
            "file_path": f"/reports/sales_{year}_{month:02d}.pdf",
        }
        return report_data


@celery_app.task  # type: ignore[untyped-decorator]
def send_order_confirmation_email(order_id: int) -> str:
    return cast(str, run_async_task(send_order_confirmation_email_async(order_id)))


@celery_app.task  # type: ignore[untyped-decorator]
def async_update_product_search_index(product_id: int) -> str:
    return cast(
        str, run_async_task(async_update_product_search_index_async(product_id))
    )


@celery_app.task  # type: ignore[untyped-decorator]
def expire_abandoned_carts() -> str:
    return cast(str, run_async_task(expire_abandoned_carts_async()))


@celery_app.task  # type: ignore[untyped-decorator]
def generate_monthly_sales_report(year: int, month: int) -> dict[str, Any]:
    return cast(
        dict[str, Any], run_async_task(generate_monthly_sales_report_async(year, month))
    )
