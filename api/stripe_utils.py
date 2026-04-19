"""Stripe helpers for Checkout, Customer Portal, and webhook processing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models import User

# In-memory idempotency store for processed webhook event IDs.
# For multi-process deployments replace with a shared store (Redis, DB table).
_processed_event_ids: set[str] = set()


def get_stripe_client():
    stripe.api_key = settings.stripe_secret_key
    stripe.api_version = settings.stripe_api_version
    return stripe


def price_id_for_tier(tier: str) -> str:
    if tier == "pro":
        return settings.stripe_price_pro
    if tier == "elite":
        return settings.stripe_price_elite
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported billing tier.")


def tier_from_price_id(price_id: str | None) -> str:
    if price_id == settings.stripe_price_elite:
        return "elite"
    if price_id == settings.stripe_price_pro:
        return "pro"
    return "free"


async def ensure_stripe_customer(user: User, db: AsyncSession) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id

    client = get_stripe_client()
    customer = client.Customer.create(
        email=user.email,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    await db.commit()
    return customer.id


async def create_checkout_session(user: User, tier: str, db: AsyncSession) -> str:
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe is not configured.")

    price_id = price_id_for_tier(tier)
    if not price_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe prices are not configured.")

    customer_id = await ensure_stripe_customer(user, db)
    client = get_stripe_client()
    session = client.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.frontend_url}/settings?checkout=success",
        cancel_url=f"{settings.frontend_url}/pricing?checkout=cancelled",
        metadata={"user_id": str(user.id), "tier": tier},
    )
    return session.url


def create_portal_session(user: User) -> str:
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe is not configured.")
    if not user.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Stripe customer is linked yet.")

    client = get_stripe_client()
    session = client.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.frontend_url}/settings",
    )
    return session.url


async def handle_webhook(payload: bytes, signature: str, db: AsyncSession) -> dict[str, bool]:
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook is not configured.")

    client = get_stripe_client()
    try:
        event = client.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook signature.") from exc

    event_id = event.get("id")
    if event_id and event_id in _processed_event_ids:
        return {"received": True}

    await apply_billing_event(event, db)

    if event_id:
        _processed_event_ids.add(event_id)

    return {"received": True}


async def apply_billing_event(event: Any, db: AsyncSession) -> None:
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        customer_id = data.get("customer")
        if not customer_id:
            return
        user = await db.scalar(select(User).where(User.stripe_customer_id == customer_id))
        if user is not None and data.get("subscription"):
            user.stripe_subscription_id = data["subscription"]
            user.subscription_status = "active"
            await db.commit()
        return

    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        customer_id = data.get("customer")
        user = await db.scalar(select(User).where(User.stripe_customer_id == customer_id))
        if user is None:
            return

        price_id = None
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")

        user.tier = tier_from_price_id(price_id)
        user.stripe_subscription_id = data.get("id")
        user.subscription_status = data.get("status")
        period_end = data.get("current_period_end")
        user.subscription_end = (
            datetime.fromtimestamp(period_end, tz=timezone.utc) if period_end else None
        )
        await db.commit()
        return

    if event_type in {"customer.subscription.deleted", "customer.subscription.paused"}:
        customer_id = data.get("customer")
        user = await db.scalar(select(User).where(User.stripe_customer_id == customer_id))
        if user is None:
            return
        user.tier = "free"
        user.subscription_status = data.get("status")
        user.stripe_subscription_id = None
        user.subscription_end = None
        await db.commit()
