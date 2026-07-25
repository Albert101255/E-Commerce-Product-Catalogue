import uuid
from typing import Any, cast

import stripe

from app.core.config import settings

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeClient:
    @staticmethod
    def create_payment_intent(
        amount_cents: int,
        currency: str = "usd",
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not settings.STRIPE_SECRET_KEY:
            # Return Mock payment intent details
            return {
                "id": f"pi_{uuid.uuid4().hex[:24]}",
                "client_secret": f"pi_secret_{uuid.uuid4().hex[:24]}",
                "status": "requires_payment_method",
                "amount": amount_cents,
                "currency": currency,
            }

        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=metadata or {},
        )
        return cast(dict[str, Any], intent)

    @staticmethod
    def confirm_payment_intent(intent_id: str, payment_method: str) -> dict[str, Any]:
        if not settings.STRIPE_SECRET_KEY:
            return {
                "id": intent_id,
                "status": "succeeded",
            }

        intent = stripe.PaymentIntent.confirm(
            intent_id,
            payment_method=payment_method,
        )
        return cast(dict[str, Any], intent)

    @staticmethod
    def create_refund(charge_id: str, amount_cents: int) -> dict[str, Any]:
        if not settings.STRIPE_SECRET_KEY:
            return {
                "id": f"re_{uuid.uuid4().hex[:24]}",
                "status": "succeeded",
                "amount": amount_cents,
            }

        refund = stripe.Refund.create(
            charge=charge_id,
            amount=amount_cents,
        )
        return cast(dict[str, Any], refund)
