import logging
import json
import time
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import settings
from app.core.limiter import limiter
from app.db import pool
from app.deps import get_current_user

logger = logging.getLogger(__name__)

# Authenticated router for user billing actions
router = APIRouter(prefix="/billing", tags=["billing"], dependencies=[Depends(get_current_user)])

# Unauthenticated / webhook router
webhook_router = APIRouter(prefix="/billing", tags=["billing"])

_price_cache = {"data": None, "timestamp": 0}


def _ensure_stripe():
    """Ensure Stripe API key is loaded from settings."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe billing is not configured on the server")
    stripe.api_key = settings.stripe_secret_key


def _fetch_stripe_price_info() -> dict:
    """Fetch live price details directly from Stripe API with 10-minute in-memory caching."""
    global _price_cache
    now = time.time()
    if _price_cache["data"] and (now - _price_cache["timestamp"] < 600):
        return _price_cache["data"]

    is_configured = bool(settings.stripe_secret_key and settings.stripe_price_id)
    if not is_configured:
        return {
            "configured": False,
            "price_id": "",
            "plan_name": "AI Pro Plan",
            "amount": 500,
            "currency": "INR",
            "interval": "month",
            "formatted_price": "₹500 / month",
        }

    try:
        _ensure_stripe()
        price = stripe.Price.retrieve(settings.stripe_price_id, expand=["product"])
        amount = (price.unit_amount or 0) / 100.0
        currency = (price.currency or "inr").upper()
        interval = price.recurring.interval if price.recurring else "month"
        product_name = price.product.name if hasattr(price.product, "name") else "AI Pro Plan"

        symbol = "₹" if currency == "INR" else "$" if currency == "USD" else f"{currency} "
        formatted = f"{symbol}{int(amount) if amount.is_integer() else amount:.2f} / {interval}"

        data = {
            "configured": True,
            "price_id": settings.stripe_price_id,
            "plan_name": product_name,
            "amount": amount,
            "currency": currency,
            "interval": interval,
            "formatted_price": formatted,
        }
        _price_cache = {"data": data, "timestamp": now}
        return data
    except Exception as e:
        logger.warning("Could not fetch price from Stripe: %s. Using fallback configuration.", e)
        return {
            "configured": True,
            "price_id": settings.stripe_price_id,
            "plan_name": "AI Pro Plan",
            "amount": 500,
            "currency": "INR",
            "interval": "month",
            "formatted_price": "₹500 / month",
        }


def _get_or_create_customer(user: dict) -> str:
    """Retrieve existing Stripe customer or create a new one, keeping customer ID cached in DB."""
    _ensure_stripe()
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT stripe_customer_id FROM subscriptions WHERE user_id = %s",
            [user["id"]]
        ).fetchone()

    if row and row["stripe_customer_id"]:
        cust_id = row["stripe_customer_id"]
        try:
            stripe.Customer.retrieve(cust_id)
            return cust_id
        except Exception:
            logger.info("Stripe customer %s not found in Stripe, creating new customer", cust_id)

    customer = stripe.Customer.create(
        email=user["email"],
        name=user.get("full_name") or None,
        metadata={"user_id": str(user["id"])},
    )
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, stripe_customer_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                stripe_customer_id = EXCLUDED.stripe_customer_id,
                updated_at = now()
            """,
            [user["id"], customer.id],
        )
    return customer.id


@router.get("/config")
def billing_config():
    """Returns dynamic billing configuration retrieved directly from Stripe."""
    return _fetch_stripe_price_info()


@router.get("/status")
def billing_status(user=Depends(get_current_user)):
    """Returns current user's subscription status."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT plan, status, current_period_end, cancel_at_period_end FROM subscriptions WHERE user_id = %s",
            [user["id"]],
        ).fetchone()

    if not row:
        return {"plan": "free", "status": "none", "current_period_end": None, "cancel_at_period_end": False}

    return dict(row)


@router.post("/checkout")
@limiter.limit("10/minute")
def create_checkout_session(request: Request, user=Depends(get_current_user)):
    """Creates a Stripe Checkout Session for upgrading to Pro Plan."""
    _ensure_stripe()
    if not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail="Stripe price ID is not configured")

    with pool.connection() as conn:
        sub = conn.execute(
            "SELECT plan, status, cancel_at_period_end FROM subscriptions WHERE user_id = %s",
            [user["id"]]
        ).fetchone()

    if sub and sub["plan"] == "pro" and sub["status"] in ("active", "trialing") and not sub.get("cancel_at_period_end"):
        raise HTTPException(status_code=400, detail="You already have an active Pro plan")

    try:
        customer_id = _get_or_create_customer(user)
        origin = settings.get_safe_frontend_origin(request)
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            success_url=f"{origin}/?billing=success",
            cancel_url=f"{origin}/?billing=cancel",
            client_reference_id=str(user["id"]),
            metadata={"user_id": str(user["id"])},
            subscription_data={"metadata": {"user_id": str(user["id"])}},
        )
    except stripe.StripeError as e:
        logger.exception("Stripe error while creating checkout session: %s", e)
        raise HTTPException(status_code=502, detail="Could not start Stripe checkout. Please try again.")

    return {"url": session.url}


@router.post("/portal")
def create_portal_session(request: Request, user=Depends(get_current_user)):
    """Creates a Stripe Customer Portal session so user can manage subscription and payment methods."""
    _ensure_stripe()
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT stripe_customer_id FROM subscriptions WHERE user_id = %s",
            [user["id"]]
        ).fetchone()

    customer_id = row["stripe_customer_id"] if row else None
    if not customer_id:
        customer_id = _get_or_create_customer(user)

    try:
        origin = settings.get_safe_frontend_origin(request)
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{origin}/?billing=portal",
        )
    except stripe.StripeError as e:
        logger.exception("Stripe error while creating portal session: %s", e)
        raise HTTPException(status_code=502, detail="Could not open Stripe billing portal. Please try again.")

    return {"url": session.url}


@router.post("/sync")
def sync_billing(user=Depends(get_current_user)):
    """Synchronizes subscription directly with Stripe. Perfect when user returns from checkout."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Billing is not configured")
    _ensure_stripe()

    with pool.connection() as conn:
        row = conn.execute(
            "SELECT stripe_customer_id, plan, status FROM subscriptions WHERE user_id = %s",
            [user["id"]],
        ).fetchone()

        customer_id = row["stripe_customer_id"] if row else None
        if not customer_id:
            try:
                custs = stripe.Customer.list(email=user["email"], limit=1)
                if custs.data:
                    customer_id = custs.data[0].id
                    conn.execute(
                        """
                        INSERT INTO subscriptions (user_id, stripe_customer_id)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET stripe_customer_id = EXCLUDED.stripe_customer_id
                        """,
                        [user["id"], customer_id],
                    )
            except Exception as e:
                logger.warning("Could not list customer for sync: %s", e)

        if customer_id:
            try:
                subs = stripe.Subscription.list(customer=customer_id, status="all", limit=1)
                if subs.data:
                    _sync_subscription(conn, subs.data[0])
            except Exception as e:
                logger.warning("Error fetching subscription for sync: %s", e)

        fresh = conn.execute(
            "SELECT plan, status, current_period_end, cancel_at_period_end FROM subscriptions WHERE user_id = %s",
            [user["id"]],
        ).fetchone()

    if not fresh:
        return {"plan": "free", "status": "none", "current_period_end": None, "cancel_at_period_end": False}
    return dict(fresh)


# -------------------------------------------------------------
# STRIPE WEBHOOK HANDLER
# -------------------------------------------------------------

SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


def _ts(value):
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except Exception:
        return None


def _extract_invoice_subscription_id(invoice: dict) -> str | None:
    """Extracts subscription ID from an invoice across different Stripe API versions."""
    sub_id = invoice.get("subscription")
    if sub_id:
        return str(sub_id)

    # Modern Stripe API versions: parent.subscription_details.subscription
    parent = invoice.get("parent") or {}
    sub_details = parent.get("subscription_details") or {}
    if sub_details.get("subscription"):
        return str(sub_details["subscription"])

    # Fallback: inspection of invoice lines data
    lines = (invoice.get("lines") or {}).get("data") or []
    for line in lines:
        if line.get("subscription"):
            return str(line["subscription"])
    return None


def _sync_subscription(conn, sub, event_created: int | None = None) -> None:
    """Synchronize a Stripe subscription object to PostgreSQL with out-of-order event protection."""
    if hasattr(sub, "to_dict"):
        sub = sub.to_dict()

    raw_status = sub.get("status") or "none"
    is_canceled = bool(
        sub.get("canceled_at")
        or sub.get("cancel_at")
        or sub.get("cancel_at_period_end")
        or raw_status in ("canceled", "unpaid", "incomplete_expired")
        or (sub.get("cancellation_details") or {}).get("reason") in ("cancellation_requested", "cancellation_scheduled")
    )

    sub_id = sub.get("id")
    customer_id = sub.get("customer")

    if is_canceled:
        plan = "free"
        status = "canceled"
        cancel_flag = True
        if raw_status != "canceled" and sub_id:
            try:
                _ensure_stripe()
                stripe.Subscription.cancel(sub_id)
            except Exception:
                pass
    elif raw_status in ("active", "trialing"):
        plan = "pro"
        status = raw_status
        cancel_flag = False
    else:
        plan = "free"
        status = raw_status
        cancel_flag = False

    period_end = sub.get("current_period_end")
    if not period_end:
        items = (sub.get("items") or {}).get("data") or []
        if items:
            period_end = items[0].get("current_period_end")

    # Out-of-order check: if event timestamp is older than current row updated_at, skip updating status
    event_dt = _ts(event_created) if event_created else None

    cur = conn.execute(
        """
        UPDATE subscriptions
        SET stripe_subscription_id = %s,
            plan = %s,
            status = %s,
            current_period_end = %s,
            cancel_at_period_end = %s,
            updated_at = now()
        WHERE stripe_customer_id = %s
          AND (%s::timestamptz IS NULL OR updated_at <= %s::timestamptz + interval '5 seconds')
        """,
        [sub_id, plan, status, _ts(period_end), cancel_flag, customer_id, event_dt, event_dt],
    )

    if cur.rowcount == 0:
        # Check if customer exists in DB first
        exists = conn.execute("SELECT 1 FROM subscriptions WHERE stripe_customer_id = %s", [customer_id]).fetchone()
        if exists:
            # Row exists but incoming event was older than current updated_at -> ignore outdated event
            logger.info("Skipped outdated Stripe event for customer %s", customer_id)
            return

        # Fallback 1: check user_id in subscription metadata
        user_id = (sub.get("metadata") or {}).get("user_id")

        # Fallback 2: retrieve customer from Stripe and inspect metadata / email
        if not (user_id and str(user_id).isdigit()) and customer_id:
            try:
                _ensure_stripe()
                cust = stripe.Customer.retrieve(customer_id)
                user_id = (cust.get("metadata") or {}).get("user_id")
                if not user_id and cust.get("email"):
                    u_row = conn.execute("SELECT id FROM users WHERE email = %s", [cust.get("email")]).fetchone()
                    if u_row:
                        user_id = u_row["id"]
            except Exception as e:
                logger.warning("Could not lookup customer %s during subscription sync: %s", customer_id, e)

        if user_id and str(user_id).isdigit():
            conn.execute(
                """
                INSERT INTO subscriptions
                    (user_id, stripe_customer_id, stripe_subscription_id, plan, status,
                     current_period_end, cancel_at_period_end, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (user_id) DO UPDATE SET
                    stripe_customer_id = COALESCE(EXCLUDED.stripe_customer_id, subscriptions.stripe_customer_id),
                    stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                    plan = EXCLUDED.plan,
                    status = EXCLUDED.status,
                    current_period_end = EXCLUDED.current_period_end,
                    cancel_at_period_end = EXCLUDED.cancel_at_period_end,
                    updated_at = now()
                """,
                [int(user_id), customer_id, sub_id, plan, status, _ts(period_end), cancel_flag],
            )
        else:
            logger.warning("Stripe subscription %s has no matching user (customer=%s)", sub_id, customer_id)


@webhook_router.post("/webhook")
async def stripe_webhook(request: Request):
    """Processes signed Stripe webhook events (checkout, subscription updates, invoices)."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event = json.loads(payload)
    event_id = event.get("id")
    event_type = event.get("type")
    event_created = event.get("created")

    try:
        with pool.connection() as conn:
            cur = conn.execute(
                "INSERT INTO stripe_events (event_id, event_type) VALUES (%s, %s) "
                "ON CONFLICT (event_id) DO NOTHING",
                [event_id, event_type],
            )
            if cur.rowcount == 0:
                return {"received": True, "duplicate": True}

            # 1. Checkout session completed -> retrieve subscription and sync
            if event_type == "checkout.session.completed":
                session_obj = event.get("data", {}).get("object", {})
                sub_id = session_obj.get("subscription")
                user_id = (session_obj.get("metadata") or {}).get("user_id") or session_obj.get("client_reference_id")
                cust_id = session_obj.get("customer")

                if sub_id:
                    _ensure_stripe()
                    actual_sub = stripe.Subscription.retrieve(sub_id)
                    if hasattr(actual_sub, "to_dict"):
                        actual_sub = actual_sub.to_dict()
                    if user_id and not (actual_sub.get("metadata") or {}).get("user_id"):
                        actual_sub.setdefault("metadata", {})["user_id"] = str(user_id)
                    _sync_subscription(conn, actual_sub, event_created=event_created)
                elif user_id and str(user_id).isdigit():
                    conn.execute(
                        """
                        INSERT INTO subscriptions (user_id, stripe_customer_id, plan, status, updated_at)
                        VALUES (%s, %s, 'pro', 'active', now())
                        ON CONFLICT (user_id) DO UPDATE SET
                            stripe_customer_id = COALESCE(EXCLUDED.stripe_customer_id, subscriptions.stripe_customer_id),
                            plan = 'pro', status = 'active', updated_at = now()
                        """,
                        [int(user_id), cust_id],
                    )

            # 2. Subscription lifecycle events
            elif event_type in SUBSCRIPTION_EVENTS:
                _sync_subscription(conn, event.get("data", {}).get("object", {}), event_created=event_created)

            # 3. Invoice payments
            elif event_type in ("invoice.payment_succeeded", "invoice.payment_failed"):
                invoice = event.get("data", {}).get("object", {})
                sub_id = _extract_invoice_subscription_id(invoice)
                if sub_id:
                    _ensure_stripe()
                    actual_sub = stripe.Subscription.retrieve(sub_id)
                    _sync_subscription(conn, actual_sub, event_created=event_created)

    except Exception:
        logger.exception("Failed to process Stripe event %s (%s)", event_id, event_type)
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"received": True}
