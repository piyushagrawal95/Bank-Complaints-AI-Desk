import logging
import json
from datetime import datetime,timezone

import stripe 
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import settings
from app.db import pool
from app.deps import get_current_user

logger=logging.getLogger(__name__)
router=APIRouter(prefix="/billing", tags=["billing"], dependencies=[Depends(get_current_user)])

stripe.api_key=settings.stripe_secret_key

def _get_or_create_customer(user:dict) -> str:
    """Every user gets exactly one Stripe customer. Reuse it if it already exists"""
    with pool.connection() as conn:
        row=conn.execute("select stripe_customer_id from subscriptions where user_id=%s",[user["id"]]).fetchone()

    if row and row["stripe_customer_id"]:
        return row["stripe_customer_id"]

    customer=stripe.Customer.create(
        email=user["email"],
        name=user.get("full_name") or None,
        metadata={"user_id":str(user["id"])}
    )
    with pool.connection() as conn:
        conn.execute("""insert into subscriptions (user_id,stripe_customer_id) values(%s,%s) on conflict(user_id) do update
        set stripe_customer_id=EXCLUDED.stripe_customer_id, updated_at=now()""",[user["id"],customer.id])
    return customer.id


@router.post("/checkout")
def create_checkout_session(request:Request, user=Depends(get_current_user)):
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise HTTPException(status_code=503,detail="Billing is not configured")

    with pool.connection() as conn:
        sub=conn.execute("select plan, status from subscriptions where user_id=%s",[user["id"]]).fetchone()

    if sub and sub["plan"]=="pro" and sub["status"] in ("active","trialing"):
        raise HTTPException(status_code=400, detail="You already have an active Pro plan")

    try:
        customer_id=_get_or_create_customer(user)
        origin=settings.get_safe_frontend_origin(request)
        session=stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price":settings.stripe_price_id,"quantity":1}],
            success_url=f"{origin}/?billing=success",
            cancel_url=f"{origin}/?billing=cancel",
            client_reference_id=str(user["id"]),
            metadata={"user_id": str(user["id"])},
            subscription_data={"metadata":{"user_id":str(user["id"])}}
        )
    except stripe.StripeError:
        logger.exception("Stripe error while creating checkout session")
        raise HTTPException(status_code=502,detail="Could not start checkout. Please try again")
    return {"url":session.url}

@router.post("/portal")
def create_portal_session(request:Request, user=Depends(get_current_user)):
    with pool.connection() as conn:
        row=conn.execute("select stripe_customer_id from subscriptions where user_id=%s",[user["id"]]).fetchone()

    if not row or not row["stripe_customer_id"]:
        raise HTTPException(status_code=400,detail="No billing account yet.Subscribe first")

    try:
        origin=settings.get_safe_frontend_origin(request)
        session=stripe.billing_portal.Session.create(
            customer=row["stripe_customer_id"],
            return_url=f"{origin}/?billing=portal"
        )

    except stripe.StripeError:
        logger.exception("Stripe error while creating portal session")
        raise HTTPException(status_code=502,detail="Could not open billing portal.Please try again")
    return {"url":session.url}

@router.get("/status")
def billing_status(user=Depends(get_current_user)):
    with pool.connection() as conn:
        row=conn.execute("select plan,status, current_period_end,cancel_at_period_end from subscriptions where user_id=%s",[user["id"]]).fetchone()

    if not row:
        return {"plan":"free","status":"none","current_period_end":None,"cancel_at_period_end":False}

    return row

# Webhook: Stripe -> our server. No JWT here (Stripe has no login token), security comes from verifying the Stripe signature instead.

webhook_router=APIRouter(prefix="/billing",tags=["billing"])

SUBSCRIPTION_EVENTS={
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted"
}

def _ts(value):
    return datetime.fromtimestamp(value,tz=timezone.utc) if value else None

def _sync_subscription(conn,sub:dict)-> None:
    status=sub.get("status") or "none"
    plan="pro" if status in ("active","trialing") else "free"

    # Newer Stripe API versions keep current_period_end on the subscription item
    period_end=sub.get("current_period_end")
    if not period_end:
        items=(sub.get("items") or {}).get("data") or []
        if items:
            period_end=items[0].get("current_period_end")

    sub_id=sub.get("id")
    customer_id=sub.get("customer")
    cancel_flag=bool(sub.get("cancel_at_period_end"))

    cur=conn.execute(
        """update subscriptions set stripe_subscription_id=%s,plan=%s,status=%s,current_period_end=%s,cancel_at_period_end=%s, updated_at=now() where stripe_customer_id=%s""",
        [sub_id,plan, status,_ts(period_end),cancel_flag,customer_id]
    )
    if cur.rowcount==0:
        #Fallback : find the user through the metadata we attached at checkout
        user_id=(sub.get("metadata") or {}).get("user_id")
        if user_id and str(user_id).isdigit():
            conn.execute(
                """
                INSERT INTO subscriptions
                    (user_id, stripe_customer_id, stripe_subscription_id, plan, status,
                     current_period_end, cancel_at_period_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    stripe_customer_id = EXCLUDED.stripe_customer_id,
                    stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                    plan = EXCLUDED.plan, status = EXCLUDED.status,
                    current_period_end = EXCLUDED.current_period_end,
                    cancel_at_period_end = EXCLUDED.cancel_at_period_end,
                    updated_at = now()
                """,
                [int(user_id), customer_id, sub_id, plan, status, _ts(period_end), cancel_flag],
            )
        else:
            logger.warning("Stripe subscription %s has no matching user", sub_id)


@webhook_router.post("/webhook")
async def stripe_webhook(request: Request):
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook is not configured")

    payload = await request.body()  # raw bytes, signature is calculated on these
    sig_header = request.headers.get("stripe-signature", "")

    try:
        stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event = json.loads(payload)  # plain dict, easy to read
    event_id, event_type = event["id"], event["type"]

    try:
        with pool.connection() as conn:  # one transaction: event log + plan update
            cur = conn.execute(
                "INSERT INTO stripe_events (event_id, event_type) VALUES (%s, %s) "
                "ON CONFLICT (event_id) DO NOTHING",
                [event_id, event_type],
            )
            if cur.rowcount == 0:
                return {"received": True, "duplicate": True}
            if event_type in SUBSCRIPTION_EVENTS:
                _sync_subscription(conn, event["data"]["object"])
    except Exception:
        logger.exception("Failed to process Stripe event %s", event_id)
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"received": True}


