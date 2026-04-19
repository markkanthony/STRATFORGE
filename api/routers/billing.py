"""Stripe subscription routes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.database import get_async_session
from api.models import User
from api.schemas import BillingStatus, CheckoutRequest, CheckoutResponse, PortalResponse
from api.stripe_utils import create_checkout_session, create_portal_session, handle_webhook


router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> CheckoutResponse:
    return CheckoutResponse(checkout_url=await create_checkout_session(user, body.tier, db))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    return await handle_webhook(payload, signature, db)


@router.get("/portal", response_model=PortalResponse)
async def portal(user: User = Depends(current_active_user)) -> PortalResponse:
    return PortalResponse(portal_url=create_portal_session(user))


@router.get("/status", response_model=BillingStatus)
async def billing_status(user: User = Depends(current_active_user)) -> BillingStatus:
    return BillingStatus(
        tier=user.tier,
        subscription_end=user.subscription_end,
        renewal_date=user.subscription_end,
        stripe_customer_id=user.stripe_customer_id,
        stripe_subscription_id=user.stripe_subscription_id,
    )
