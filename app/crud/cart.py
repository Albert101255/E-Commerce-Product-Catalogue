from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart, CartItem
from app.models.product import ProductVariant
from app.schemas.cart import CartItemBase


async def get_user_cart(db: AsyncSession, user_id: int) -> Cart:
    # 1. Fetch cart
    result = await db.execute(
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(selectinload(Cart.items).selectinload(CartItem.variant))
    )
    cart = result.scalar_one_or_none()

    now = datetime.now(UTC)
    if cart and cart.expires_at.tzinfo is None:
        now = now.replace(tzinfo=None)

    if not cart:
        # Create new cart
        cart = Cart(user_id=user_id, expires_at=now + timedelta(days=7))
        db.add(cart)
        await db.flush()
        # Eager load items list
        await db.refresh(cart, ["items"])
    elif cart.expires_at < now:
        # Cart expired, clear items and extend expiration
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        cart.expires_at = now + timedelta(days=7)
        db.add(cart)
        await db.flush()
        await db.refresh(cart, ["items"])

    return cart


async def add_item_to_cart(
    db: AsyncSession, user_id: int, item_in: CartItemBase
) -> CartItem:
    cart = await get_user_cart(db, user_id=user_id)

    # Check if variant exists and get its current price
    var_result = await db.execute(
        select(ProductVariant).where(ProductVariant.id == item_in.product_variant_id)
    )
    variant = var_result.scalar_one_or_none()
    if not variant:
        raise ValueError("Product variant not found")

    # Check if item already exists in cart
    existing_item = next(
        (
            item
            for item in cart.items
            if item.product_variant_id == item_in.product_variant_id
        ),
        None,
    )

    if existing_item:
        existing_item.quantity += item_in.quantity
        existing_item.price_at_add = variant.price  # Update snapshot price to current
        db.add(existing_item)
        db_obj = existing_item
    else:
        db_obj = CartItem(
            cart_id=cart.id,
            product_variant_id=item_in.product_variant_id,
            quantity=item_in.quantity,
            price_at_add=variant.price,
        )
        db.add(db_obj)

    await db.flush()
    await db.refresh(db_obj, ["variant"])

    # Record metric
    from app.core.monitoring import CART_ADDITIONS

    CART_ADDITIONS.inc()

    return db_obj


async def remove_item_from_cart(db: AsyncSession, user_id: int, item_id: int) -> bool:
    cart = await get_user_cart(db, user_id=user_id)
    # Check if item exists in this user's cart
    result = await db.execute(
        select(CartItem)
        .where(CartItem.id == item_id)
        .where(CartItem.cart_id == cart.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return False

    await db.delete(item)
    await db.flush()
    return True


async def clear_cart(db: AsyncSession, user_id: int) -> None:
    cart = await get_user_cart(db, user_id=user_id)
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.flush()
