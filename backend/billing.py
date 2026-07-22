"""Stripe billing — Phase 1 architecture stub (NO payment functionality wired).

This module intentionally does NOT process real payments. It exists so that
future phases can plug Stripe in without restructuring the app. When ready,
implement checkout session creation, webhook handler and subscription sync
here, then include this router in server.py.

Env variables (add when activating):
  STRIPE_SECRET_KEY   - Secret key (sk_test_… / sk_live_…)
  STRIPE_WEBHOOK_SECRET - Webhook signing secret
  STRIPE_PRICE_PRO        - Price ID for Pro plan
  STRIPE_PRICE_BUSINESS   - Price ID for Business plan

Mongo collections (to be created when activating):
  stripe_customers       { user_id, customer_id, created_at }
  stripe_subscriptions   { user_id, subscription_id, price_id, status, current_period_end }
  payments               { user_id, amount_inr, currency, status, created_at }
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/status")
async def billing_status():
    """Reports whether payments are enabled. Always False in Phase 1."""
    return {"enabled": False, "phase": "waitlist"}


@router.post("/checkout")
async def create_checkout_session():
    raise HTTPException(501, "Payments are not enabled yet. Join the waitlist.")


@router.post("/webhook")
async def stripe_webhook():
    raise HTTPException(501, "Stripe webhook not enabled yet.")
