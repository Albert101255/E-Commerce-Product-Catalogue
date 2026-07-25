from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user, get_current_user
from app.db.base import get_db
from app.models.payment import PaymentMethod, Transaction
from app.models.user import User
from app.schemas.payment import (
    PaymentMethodCreate,
    PaymentMethodOut,
    ProcessPayment,
    RefundCreate,
    RefundOut,
    TransactionOut,
)
from app.services.payment_service import process_order_payment, refund_order

router = APIRouter()


@router.post(
    "/payment-methods",
    response_model=PaymentMethodOut,
    status_code=status.HTTP_201_CREATED,
)
async def save_payment_method(
    pm_in: PaymentMethodCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Save a mock card/Stripe payment method token for a user.
    """
    # Simply create the payment method with last_four extracted or mocked
    # In real setup we would request Stripe API details using
    # pm_in.stripe_payment_method_id
    pm = PaymentMethod(
        user_id=current_user.id,
        type=pm_in.type,
        last_four="4242",  # mocked
        is_default=pm_in.is_default,
    )
    db.add(pm)
    await db.flush()
    await db.refresh(pm)
    return pm


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
async def list_payment_methods(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    List user's saved payment methods.
    """
    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.user_id == current_user.id)
        .where(PaymentMethod.is_active.is_(True))
    )
    return list(result.scalars().all())


@router.delete("/payment-methods/{pm_id}", status_code=status.HTTP_200_OK)
async def delete_payment_method(
    pm_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """
    Soft-delete/disable a saved payment method.
    """
    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.id == pm_id)
        .where(PaymentMethod.user_id == current_user.id)
    )
    pm = result.scalar_one_or_none()
    if not pm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found",
        )
    pm.is_active = False
    db.add(pm)
    await db.flush()
    return {"message": "Payment method removed"}


@router.post("/checkout/process", response_model=TransactionOut)
async def process_payment(
    payment_in: ProcessPayment,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Process payment for a pending order.
    """
    try:
        return await process_order_payment(
            db, user_id=current_user.id, payment_in=payment_in
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None


@router.get("/orders/{order_id}/payment-status", response_model=list[TransactionOut])
async def get_payment_status(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Get transactions history for a specific order.
    """
    # Fetch transactions
    result = await db.execute(
        select(Transaction)
        .where(Transaction.order_id == order_id)
        .order_by(Transaction.created_at.desc())
    )
    txs = list(result.scalars().all())
    if not txs:
        # Check if order exists
        from app.crud.order import get_order_by_id

        order = await get_order_by_id(db, order_id=order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )
        if order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view status for this order",
            )
    return txs


@router.post(
    "/orders/{order_id}/refund",
    response_model=RefundOut,
    status_code=status.HTTP_201_CREATED,
)
async def refund_order_route(
    order_id: int,
    refund_in: RefundCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> Any:
    """
    Refund a paid order. Admins only.
    """
    try:
        return await refund_order(db, order_id=order_id, refund_in=refund_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None
