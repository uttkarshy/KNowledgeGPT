import hashlib
import hmac

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.billing import CreditPurchase
from app.models.user import User
from app.schemas.billing import CreditSummary, CreditUsagePublic
from app.services.credit_service import recent_usage

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CreateOrderRequest(BaseModel):
    pack_code: str


@router.get("/credits", response_model=CreditSummary)
async def credits(current_user: User = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    return CreditSummary(
        balance=current_user.credit_balance,
        plan_code=current_user.plan_code,
        starter_allowance=settings.STARTER_CREDITS,
        chat_credits=settings.CHAT_CREDITS,
        document_credits_per_page=settings.DOCUMENT_CREDITS_PER_PAGE,
        payments_enabled=bool(settings.CREDIT_PACKS and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET and settings.RAZORPAY_WEBHOOK_SECRET),
    )


@router.get("/usage", response_model=list[CreditUsagePublic])
async def usage(
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await recent_usage(db, user_id=current_user.id, limit=limit)


@router.get("/packs")
async def packs(settings: Settings = Depends(get_settings)):
    return [{"code": code, **details} for code, details in settings.CREDIT_PACKS.items()]


@router.post("/orders")
async def create_order(
    body: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(503, "Credit purchases are not configured")
    pack = settings.CREDIT_PACKS.get(body.pack_code)
    if not pack or pack.get("credits", 0) <= 0 or pack.get("amount_paise", 0) <= 0:
        raise HTTPException(400, "Unknown credit pack")
    purchase = CreditPurchase(
        user_id=current_user.id, pack_code=body.pack_code,
        credits=pack["credits"], amount_paise=pack["amount_paise"],
    )
    db.add(purchase)
    await db.flush()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.razorpay.com/v1/orders",
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                json={"amount": purchase.amount_paise, "currency": "INR", "receipt": str(purchase.id),
                      "notes": {"purchase_id": str(purchase.id)}},
            )
            response.raise_for_status()
            order = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(502, "Payment provider is unavailable. No credits were charged.") from exc
    purchase.provider_order_id = order["id"]
    await db.commit()
    return {"purchase_id": purchase.id, "order_id": purchase.provider_order_id,
            "amount_paise": purchase.amount_paise, "currency": "INR", "key_id": settings.RAZORPAY_KEY_ID}


@router.post("/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(503, "Payment webhook is not configured")
    raw = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(400, "Invalid webhook signature")
    payload = await request.json()
    if payload.get("event") != "payment.captured":
        return {"accepted": True}
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = payment.get("order_id")
    purchase = await db.scalar(select(CreditPurchase).where(
        CreditPurchase.provider_order_id == order_id
    ).with_for_update())
    if not purchase:
        raise HTTPException(404, "Purchase not found")
    if payment.get("amount") != purchase.amount_paise or payment.get("currency") != "INR":
        raise HTTPException(400, "Payment amount does not match the order")
    payment_id = str(payment.get("id", ""))
    if purchase.status == "captured":
        return {"accepted": True}
    if not payment_id:
        raise HTTPException(400, "Payment id is missing")
    purchase.status = "captured"
    purchase.provider_payment_id = payment_id
    from app.services.credit_service import grant
    await grant(
        db, user_id=purchase.user_id, credits=purchase.credits,
        operation="credits.purchase", idempotency_key=f"razorpay:{payment_id}",
        metadata={"purchase_id": str(purchase.id), "order_id": order_id},
    )
    await db.commit()
    return {"accepted": True}
