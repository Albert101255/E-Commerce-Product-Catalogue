from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.stripe_client import StripeClient
from app.crud.order import update_order_status
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import (
    PaymentMethod,
    PaymentMethodType,
    Refund,
    Transaction,
    TransactionStatus,
)
from app.schemas.payment import ProcessPayment, RefundCreate


async def process_order_payment(
    db: AsyncSession, user_id: int, payment_in: ProcessPayment
) -> Transaction:
    # 1. Fetch Order
    order_result = await db.execute(
        select(Order)
        .where(Order.id == payment_in.order_id)
        .options(selectinload(Order.items))
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise ValueError("Order not found")
    if order.user_id != user_id:
        raise ValueError("Not authorized to pay for this order")
    if order.status != OrderStatus.PENDING:
        raise ValueError(f"Order cannot be paid in status '{order.status.value}'")

    pm_id = None

    if payment_in.payment_method_id:
        pm_result = await db.execute(
            select(PaymentMethod)
            .where(PaymentMethod.id == payment_in.payment_method_id)
            .where(PaymentMethod.user_id == user_id)
        )
        pm = pm_result.scalar_one_or_none()
        if not pm:
            raise ValueError("Payment method not found")
        pm_id = pm.id
    elif payment_in.stripe_token:
        # Mock token, save new PaymentMethod
        # Extract last 4 if possible or mock
        pm = PaymentMethod(
            user_id=user_id,
            type=PaymentMethodType.STRIPE,
            last_four="4242",
            is_default=True,
        )
        db.add(pm)
        await db.flush()
        pm_id = pm.id

    # 3. Create Stripe Payment Intent (convert dollars to cents)
    amount_cents = int(round(order.total * 100))

    try:
        intent = StripeClient.create_payment_intent(
            amount_cents=amount_cents,
            currency="usd",
            metadata={"order_id": str(order.id)},
        )

        # Confirm intent automatically for simplicity in mock/test
        confirm = StripeClient.confirm_payment_intent(
            intent["id"], payment_method="pm_card_visa"
        )

        if confirm["status"] == "succeeded":
            transaction = Transaction(
                order_id=order.id,
                payment_method_id=pm_id,
                amount=order.total,
                status=TransactionStatus.COMPLETED,
                external_transaction_id=confirm["id"],
            )
            db.add(transaction)
            await update_order_status(db, order=order, new_status=OrderStatus.CONFIRMED)
        else:
            transaction = Transaction(
                order_id=order.id,
                payment_method_id=pm_id,
                amount=order.total,
                status=TransactionStatus.FAILED,
                error_message=f"Stripe status: {confirm['status']}",
            )
            db.add(transaction)
    except Exception as e:
        transaction = Transaction(
            order_id=order.id,
            payment_method_id=pm_id,
            amount=order.total,
            status=TransactionStatus.FAILED,
            error_message=str(e),
        )
        db.add(transaction)

    await db.flush()
    await db.refresh(transaction)
    return transaction


async def refund_order(
    db: AsyncSession, order_id: int, refund_in: RefundCreate
) -> Refund:
    order_result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items).selectinload(OrderItem.variant))
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise ValueError("Order not found")

    valid_statuses = [
        OrderStatus.CONFIRMED,
        OrderStatus.PROCESSING,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
    ]
    if order.status not in valid_statuses:
        raise ValueError(f"Order cannot be refunded in status '{order.status.value}'")

    # Get successful transaction
    tx_result = await db.execute(
        select(Transaction)
        .where(Transaction.order_id == order_id)
        .where(Transaction.status == TransactionStatus.COMPLETED)
    )
    transaction = tx_result.scalar_one_or_none()
    if not transaction:
        raise ValueError("Successful transaction not found for this order")

    if refund_in.amount > order.total:
        raise ValueError(f"Refund amount cannot exceed order total ({order.total})")

    amount_cents = int(round(refund_in.amount * 100))
    charge_id = transaction.external_transaction_id or "ch_mock"

    # Process Stripe Refund
    StripeClient.create_refund(charge_id=charge_id, amount_cents=amount_cents)

    refund = Refund(
        transaction_id=transaction.id,
        order_id=order.id,
        amount=refund_in.amount,
        reason=refund_in.reason,
        status="COMPLETED",
    )
    db.add(refund)

    # Update transaction status
    transaction.status = TransactionStatus.REFUNDED
    db.add(transaction)

    # Update order status -> this will automatically restore stock in
    # update_order_status CRUD helper
    await update_order_status(db, order=order, new_status=OrderStatus.REFUNDED)

    await db.flush()
    await db.refresh(refund)
    return refund
