"""Tiny demo API surface used by the Commons multi-agent demo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentIntent:
    intent_id: str
    amount_cents: int
    currency: str
    status: str = "created"


def create_payment_intent(intent_id: str, amount_cents: int, currency: str = "USD") -> PaymentIntent:
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive")
    return PaymentIntent(intent_id=intent_id, amount_cents=amount_cents, currency=currency)


def summarize(intent: PaymentIntent) -> str:
    return f"{intent.intent_id}:{intent.amount_cents}:{intent.currency}:{intent.status}"
