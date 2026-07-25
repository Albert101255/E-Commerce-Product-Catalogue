from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentMethodType, TransactionStatus


# Payment Method Schemas
class PaymentMethodBase(BaseModel):
    type: PaymentMethodType = PaymentMethodType.STRIPE
    last_four: str
    is_default: bool = False
    is_active: bool = True


class PaymentMethodCreate(BaseModel):
    type: PaymentMethodType = PaymentMethodType.STRIPE
    stripe_payment_method_id: str  # Stripe PM token (e.g., pm_123)
    is_default: bool = False


class PaymentMethodOut(PaymentMethodBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


# Transaction Schemas
class TransactionOut(BaseModel):
    id: int
    order_id: int
    payment_method_id: int | None = None
    amount: float
    status: TransactionStatus
    error_message: str | None = None
    external_transaction_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Refund Schemas
class RefundCreate(BaseModel):
    amount: float
    reason: str


class RefundOut(BaseModel):
    id: int
    transaction_id: int
    order_id: int
    amount: float
    reason: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Process Payment request schema
class ProcessPayment(BaseModel):
    order_id: int
    payment_method_id: int | None = None
    stripe_token: str | None = None  # Mock/Real token
