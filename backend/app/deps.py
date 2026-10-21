import logging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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
                "SELECT id, email, full_name, role, is_active FROM users WHERE id = %s",
                [user_id],
            ).fetchone()
    except Exception:
        logger.exception("Database error while reading the current user")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if user is None or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Account not found or disabled")
    return user


def require_role(*roles: str):
    """Allow only users whose role is in `roles`, otherwise raise 403."""
    def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission to do this")
        return user
    return checker
