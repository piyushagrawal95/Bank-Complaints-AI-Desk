import logging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.db import pool
from app.security import decode_access_token

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """Returns the logged in user or raises 401."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Not logged in")

    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        with pool.connection() as conn:
            user = conn.execute(
                """
                SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.token_version,
                       COALESCE(s.plan, 'free') AS plan,
                       COALESCE(s.status, 'none') AS subscription_status,
                       s.current_period_end,
                       s.cancel_at_period_end
                FROM users u
                LEFT JOIN subscriptions s ON u.id = s.user_id
                WHERE u.id = %s
                """,
                [user_id],
            ).fetchone()
    except Exception:
        # Fallback if subscriptions table or token_version column is not yet migrated in old schema
        try:
            with pool.connection() as conn:
                user = conn.execute(
                    "SELECT id, email, full_name, role, is_active FROM users WHERE id = %s",
                    [user_id],
                ).fetchone()
                if user:
                    user = dict(user)
                    user.setdefault("plan", "free")
                    user.setdefault("subscription_status", "none")
                    user.setdefault("current_period_end", None)
                    user.setdefault("cancel_at_period_end", False)
        except Exception:
            logger.exception("Database error while reading the current user")
            raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if user is None:
        raise HTTPException(status_code=401, detail="Account not found")

    # Invalidate token if token_version does not match (e.g. password was reset)
    token_tv = payload.get("tv")
    db_tv = user.get("token_version")
    if token_tv is not None and db_tv is not None and token_tv != db_tv:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    # Enforce permanent super admin rights strictly from environment config
    super_admin = (settings.super_admin_email or "").strip().lower()
    if super_admin and user["email"].lower() == super_admin:
        needs_db_fix = (user.get("role") != "admin" or not user.get("is_active"))
        user["role"] = "admin"
        user["is_active"] = True
        # Note: plan and subscription_status reflect actual database subscription state
        if needs_db_fix:
            try:
                with pool.connection() as fix_conn:
                    fix_conn.execute(
                        "UPDATE users SET role = 'admin', is_active = true WHERE id = %s",
                        [user["id"]],
                    )
            except Exception:
                pass

    if not user["is_active"]:
        raise HTTPException(status_code=401, detail="Account disabled")
    return user


def require_role(*roles: str):
    """Allow only users whose role is in `roles`, otherwise raise 403."""
    def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission to do this")
        return user
    return checker


def require_pro(user=Depends(get_current_user)):
    """Enforce active Pro subscription plan. Canceled subscriptions revert to Free."""
    is_pro = user.get("plan") == "pro" and user.get("subscription_status") in ("active", "trialing")

    if is_pro:
        return user

    raise HTTPException(
        status_code=402,
        detail="This feature requires an active Pro Plan subscription. Please upgrade to unlock.",
    )
