from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.cart import clear_cart, get_user_cart
from app.models.order import (
    Order,
    OrderFulfillment,
    OrderItem,
    OrderReturn,
    OrderStatus,
    ReturnStatus,
)
from app.models.warehouse import Warehouse
from app.schemas.order import OrderCreate, OrderReturnCreate, WarehouseCreate


async def get_order_by_id(db: AsyncSession, order_id: int) -> Order | None:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .where(Order.deleted_at.is_(None))
        .options(
            selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.fulfillments).selectinload(OrderFulfillment.warehouse),
            selectinload(Order.returns),
        )
    )
    return result.scalar_one_or_none()


async def get_user_orders(db: AsyncSession, user_id: int) -> list[Order]:
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .where(Order.deleted_at.is_(None))
        .options(
            selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.fulfillments),
            selectinload(Order.returns),
        )
    )
    return list(result.scalars().all())


async def create_order_from_cart(
    db: AsyncSession, user_id: int, order_in: OrderCreate
) -> Order:
    import random
    import time
    from datetime import UTC, datetime

    from app.core.monitoring import CHECKOUT_LATENCY, ORDER_COUNT

    start_checkout = time.perf_counter()
    try:
        # 1. Fetch user's cart
        cart = await get_user_cart(db, user_id=user_id)
        if not cart.items:
            raise ValueError("Cannot checkout an empty cart")

        # 2. Validate stock for all items
        for item in cart.items:
            if item.variant.quantity_in_stock < item.quantity:
                raise ValueError(
                    f"Insufficient stock for variant '{item.variant.name}'. "
                    f"Available: {item.variant.quantity_in_stock}, "
                    f"requested: {item.quantity}"
                )

        # 3. Deduct stock
        for item in cart.items:
            item.variant.quantity_in_stock -= item.quantity
            db.add(item.variant)

        # 4. Calculate amounts
        subtotal = sum(item.price_at_add * item.quantity for item in cart.items)
        shipping_amount = 0.0 if subtotal > 100.0 else 5.0
        tax_amount = round(subtotal * 0.08, 2)  # 8% tax rate
        total = subtotal + shipping_amount + tax_amount

        # 5. Create Order
        now_str = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        rand_val = random.randint(1000, 9999)
        order_number = f"ORD-{now_str}-{rand_val}"
        order = Order(
            order_number=order_number,
            user_id=user_id,
            status=OrderStatus.PENDING,
            subtotal=subtotal,
            shipping_amount=shipping_amount,
            tax_amount=tax_amount,
            discount_amount=0.0,
            total=total,
            shipping_address=order_in.shipping_address,
            billing_address=order_in.billing_address,
        )
        db.add(order)
        await db.flush()

        # 6. Create OrderItem records & snapshot prices
        for item in cart.items:
            order_item = OrderItem(
                order_id=order.id,
                product_variant_id=item.product_variant_id,
                quantity=item.quantity,
                unit_price=item.price_at_add,
            )
            db.add(order_item)

        await db.flush()

        # 7. Clear cart
        await clear_cart(db, user_id=user_id)

        # Refresh to load relationships
        db_result = await db.execute(
            select(Order)
            .where(Order.id == order.id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.variant),
                selectinload(Order.fulfillments),
                selectinload(Order.returns),
            )
        )
        order_obj = db_result.scalar_one()
        from app.tasks.celery_tasks import send_order_confirmation_email

        send_order_confirmation_email.delay(order_obj.id)

        # Record success metrics
        ORDER_COUNT.labels(status="placed").inc()
        CHECKOUT_LATENCY.observe(time.perf_counter() - start_checkout)

        return order_obj
    except Exception as e:
        # Record failure metrics
        ORDER_COUNT.labels(status="failed").inc()
        raise e


async def update_order_status(
    db: AsyncSession, order: Order, new_status: OrderStatus
) -> Order:
    old_status = order.status
    if old_status == new_status:
        return order

    # If transitioning to CANCELLED or REFUNDED, we restore stock
    if new_status in [OrderStatus.CANCELLED, OrderStatus.REFUNDED]:
        # Only restore stock if we haven't already restored it
        if old_status not in [OrderStatus.CANCELLED, OrderStatus.REFUNDED]:
            for item in order.items:
                item.variant.quantity_in_stock += item.quantity
                db.add(item.variant)

    order.status = new_status
    if new_status == OrderStatus.SHIPPED:
        order.shipped_at = datetime.now(UTC)
    elif new_status == OrderStatus.DELIVERED:
        order.delivered_at = datetime.now(UTC)

    db.add(order)
    await db.flush()
    db_result = await db.execute(
        select(Order)
        .where(Order.id == order.id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.fulfillments).selectinload(OrderFulfillment.warehouse),
            selectinload(Order.returns),
        )
    )
    return db_result.scalar_one()


async def create_order_return(
    db: AsyncSession, order: Order, user_id: int, return_in: OrderReturnCreate
) -> OrderReturn:
    # Find matching OrderItem
    item = next((i for i in order.items if i.id == return_in.order_item_id), None)
    if not item:
        raise ValueError("Item not found in this order")

    # Validate quantity
    if return_in.quantity > item.quantity:
        raise ValueError(
            f"Cannot return more than purchased quantity ({item.quantity})"
        )

    # Calculate refund amount
    refund_amount = round(item.unit_price * return_in.quantity, 2)

    db_obj = OrderReturn(
        order_id=order.id,
        order_item_id=return_in.order_item_id,
        status=ReturnStatus.REQUESTED,
        reason=return_in.reason,
        quantity=return_in.quantity,
        refund_amount=refund_amount,
    )
    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    return db_obj


# Warehouse CRUD
async def get_warehouse_by_id(db: AsyncSession, warehouse_id: int) -> Warehouse | None:
    result = await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))
    return result.scalar_one_or_none()


async def create_warehouse(db: AsyncSession, obj_in: WarehouseCreate) -> Warehouse:
    db_obj = Warehouse(**obj_in.model_dump())
    db.add(db_obj)
    await db.flush()
    await db.refresh(db_obj)
    return db_obj


async def get_warehouses(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[Warehouse]:
    result = await db.execute(select(Warehouse).offset(skip).limit(limit))
    return list(result.scalars().all())
