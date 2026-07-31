"""Razorpay credit-pack purchases.

This router is a FEATURE FLAG: every endpoint returns 503 if RAZORPAY_KEY_ID
isn't set. That way the code is ready to ship the moment ops set the two
env vars — no additional deploy needed.

Env variables (set to activate):
  RAZORPAY_KEY_ID          - Test-mode: rzp_test_… / Live: rzp_live_…
  RAZORPAY_KEY_SECRET      - The corresponding secret (server-side only)
  RAZORPAY_WEBHOOK_SECRET  - Optional. If set, /webhook signature-verifies.
  RAZORPAY_LIVE_MODE       - Optional flag ("1" to hide test-mode banner).

Frontend integration:
  Uses Razorpay Checkout.js loaded on demand from https://checkout.razorpay.com/v1/checkout.js
  See /app/frontend/src/lib/razorpayCheckout.js

Mongo collections created on demand:
  payments — one doc per order attempt (created/paid/failed)
"""
from __future__ import annotations
import os
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/payments/razorpay", tags=["payments"])


def _current_user_dep():
    """FastAPI dependency wrapper — resolves `current_user` lazily to avoid the
    circular import (server.py imports this router at boot). We return the raw
    dependency callable so FastAPI does its own signature-based resolution."""
    from server import current_user  # type: ignore
    return current_user


# Credit-pack catalogue. Amounts are in INR (rupees). The frontend uses this
# to render the pricing tiles and pass a valid pack_id to /create-order.
# ContentOS AI · Part B pricing — synced with GET /api/pricing/config packs.
CREDIT_PACKS = [
    {"id": "micro",  "credits":  100, "price_inr":  999, "label": "Micro Pack"},
    {"id": "growth", "credits":  500, "price_inr": 3999, "label": "Growth Pack", "popular": True},
    {"id": "power",  "credits": 1500, "price_inr": 9999, "label": "Power Pack"},
]
PACKS_BY_ID = {p["id"]: p for p in CREDIT_PACKS}


def _is_configured() -> bool:
    return bool(os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))


def _client():
    if not _is_configured():
        raise HTTPException(503, "Payments are not activated yet — check back soon.")
    import razorpay
    return razorpay.Client(auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))


@router.get("/config")
async def payment_config():
    """Public config for the frontend. Never returns the secret."""
    return {
        "enabled": _is_configured(),
        "live_mode": os.environ.get("RAZORPAY_LIVE_MODE") == "1",
        "key_id": os.environ.get("RAZORPAY_KEY_ID") if _is_configured() else None,
        "packs": CREDIT_PACKS,
        "currency": "INR",
    }


class CreateOrderIn(BaseModel):
    pack_id: str


def _require_user(request: Request):
    """Local user resolver — imported lazily to avoid circular imports.
    Delegates to the same current_user dep used by server.py."""
    from server import current_user  # type: ignore
    return current_user


@router.post("/create-order")
async def create_order(payload: CreateOrderIn,
                       user=Depends(_current_user_dep())):
    """Creates a Razorpay order for the requested credit pack and returns the
    order details the frontend needs to launch Checkout.js."""
    from server import db  # type: ignore
    if not _is_configured():
        raise HTTPException(503, "Payments are not activated yet — check back soon.")
    pack = PACKS_BY_ID.get(payload.pack_id)
    if not pack:
        raise HTTPException(400, "Unknown credit pack.")
    client = _client()
    amount_paise = int(pack["price_inr"]) * 100
    receipt = f"pack_{pack['id']}_{user['user_id'][:14]}_{int(datetime.now().timestamp())}"[:40]
    try:
        rzp_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "user_id": user["user_id"],
                "pack_id": pack["id"],
                "credits": str(pack["credits"]),
            },
            "payment_capture": 1,
        })
    except Exception as e:
        logger.exception("razorpay_order_create_failed user=%s pack=%s", user["user_id"], pack["id"])
        raise HTTPException(502, f"Couldn't create order — try again in a moment.")

    # Persist a pending payment record so we can reconcile even if the user
    # closes the tab before /verify fires.
    await db.payments.insert_one({
        "user_id": user["user_id"],
        "order_id": rzp_order["id"],
        "pack_id": pack["id"],
        "credits": pack["credits"],
        "amount_inr": pack["price_inr"],
        "amount_paise": amount_paise,
        "currency": "INR",
        "status": "created",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "order_id": rzp_order["id"],
        "amount": rzp_order["amount"],
        "currency": rzp_order["currency"],
        "key_id": os.environ["RAZORPAY_KEY_ID"],
        "pack": pack,
        "prefill": {
            "name": user.get("name") or "",
            "email": user.get("email") or "",
        },
    }


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/verify")
async def verify_payment(payload: VerifyIn,
                         user=Depends(_current_user_dep())):
    """Client-side callback after Checkout.js completes. We verify the HMAC
    signature and, on success, grant the credits + mark the payment paid.
    Idempotent: repeat calls for the same order_id return a 'paid' result
    without double-crediting."""
    from server import db  # type: ignore
    if not _is_configured():
        raise HTTPException(503, "Payments are not activated yet.")

    # Look up the pending payment doc — safety net so a signed request from a
    # different user can never grant credits to the wrong account.
    pending = await db.payments.find_one({"order_id": payload.razorpay_order_id, "user_id": user["user_id"]}, {"_id": 0})
    if not pending:
        raise HTTPException(404, "Order not found for this user.")
    if pending.get("status") == "paid":
        return {"status": "paid", "credits_granted": 0, "idempotent": True}

    # HMAC-SHA256(secret, order_id + '|' + payment_id) must match signature
    body = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}"
    secret = os.environ["RAZORPAY_KEY_SECRET"].encode()
    expected = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, payload.razorpay_signature):
        logger.warning("razorpay_sig_mismatch user=%s order=%s", user["user_id"], payload.razorpay_order_id)
        await db.payments.update_one(
            {"order_id": payload.razorpay_order_id},
            {"$set": {"status": "signature_failed"}},
        )
        raise HTTPException(400, "Payment signature verification failed.")

    credits = int(pending["credits"])
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"credits": credits, "credits_purchased": credits}},
    )
    await db.payments.update_one(
        {"order_id": payload.razorpay_order_id},
        {"$set": {
            "status": "paid",
            "payment_id": payload.razorpay_payment_id,
            "paid_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"status": "paid", "credits_granted": credits, "idempotent": False}


@router.post("/webhook")
async def razorpay_webhook(request: Request):
    """Server-to-server fallback in case the /verify roundtrip is missed
    (browser closed, mid-flight network error). Verifies the raw-body HMAC
    against RAZORPAY_WEBHOOK_SECRET and grants credits on `payment.captured`.
    Idempotent — dedupes on order_id."""
    from server import db  # type: ignore
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    payload_bytes = await request.body()
    if secret:
        sig = request.headers.get("x-razorpay-signature") or ""
        expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(400, "Bad signature.")
    try:
        import json
        payload = json.loads(payload_bytes)
    except Exception:
        raise HTTPException(400, "Bad payload.")

    event = payload.get("event", "")
    if event == "payment.captured":
        p = payload.get("payload", {}).get("payment", {}).get("entity", {}) or {}
        order_id = p.get("order_id")
        payment_id = p.get("id")
        pending = await db.payments.find_one({"order_id": order_id}, {"_id": 0}) if order_id else None
        if pending and pending.get("status") != "paid":
            await db.users.update_one(
                {"user_id": pending["user_id"]},
                {"$inc": {"credits": int(pending["credits"]),
                          "credits_purchased": int(pending["credits"])}},
            )
            await db.payments.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": "paid",
                    "payment_id": payment_id,
                    "paid_at": datetime.now(timezone.utc).isoformat(),
                    "via": "webhook",
                }},
            )
    return {"ok": True}
