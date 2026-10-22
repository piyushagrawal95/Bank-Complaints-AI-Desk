from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings
from app.db import pool
from app.deps import get_current_user, require_role
from app.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

class GoogleLoginIn(BaseModel):
    credential:str




class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)


class RoleUpdateIn(BaseModel):
    user_id: int
    role: str = Field(pattern="^(agent|supervisor|admin)$")


@router.post("/signup", status_code=201)
def signup(body: SignupIn):
    email = body.email.lower()
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO users (email, password_hash, full_name, role) "
                "VALUES (%s, %s, %s, 'agent') ON CONFLICT (email) DO NOTHING "
                "RETURNING id, email, full_name, role",
                [email, hash_password(body.password), body.full_name],
            ).fetchone()
    except Exception as exc:
        logger.exception("Database error during signup")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if row is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    return row


@router.post("/login")
def login(body: LoginIn):
    email = body.email.lower()
    try:
        with pool.connection() as conn:
            user = conn.execute(
                "SELECT id, email, full_name, role, is_active, password_hash "
                "FROM users WHERE email = %s",
                [email],
            ).fetchone()
    except Exception as exc:
        logger.exception("Database error during login")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if (
        user is None
        or not user["is_active"]
        or not verify_password(body.password, user["password_hash"])
    ):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    try:
        token = create_access_token(user["id"], user["role"])
    except RuntimeError:
        logger.exception("Could not create token")
        raise HTTPException(status_code=500, detail="Login is not configured on the server")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
        },
    }

@router.post("/google")
def login_with_google(body:GoogleLoginIn):
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip() or None
    try:
        #Google ka official token verification
        idinfo=id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            client_id
        )

    except Exception as exc:
        logger.exception("Google token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail=f"Google authentication failed: {exc}")

    email=idinfo["email"].lower()
    full_name=idinfo.get("name","Google User")

    with pool.connection() as conn:
        #user check krenge ki database m h ya nahi
        user=conn.execute(
            "select id, email,full_name, role,is_active from users where email=%s",[email]
        ).fetchone()

        #agar user nahi mila to naya account create kro
        if not user:
            user=conn.execute(
                "insert into users(email,password_hash,full_name,role) values(%s,'oauth_google',%s,'agent') returning id, email, full_name, role,is_active",
                [email,full_name]
            ).fetchone()

    if not user["is_active"]:
        raise HTTPException(status_code=403,detail="Your account has been deactivated")

    #Bank system ka standard Jwt access token issue krenge
    token=create_access_token(user["id"],user["role"])

    return{
        "access_token":token,
        "token_type":"bearer",
        "user":{
            "id":user["id"],
            "email":user["email"],
            "full_name":user["full_name"],
            "role":user["role"]
        }

    }


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user


def send_password_reset_email(to_email: str, raw_token: str):
    """Sends a professional password reset email with a 15-minute secure link."""
    frontend_url = settings.frontend_origin
    reset_link = f"{frontend_url}/?reset_token={raw_token}"

    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not smtp_user or not smtp_password:
        logger.info(f"SMTP not configured in .env. Dev password reset link for {to_email}: {reset_link}")
        return

    subject = "Reset Your Password - Bank Complaint AI Desk"
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6; background: #f8fafc; padding: 20px;">
        <div style="max-width: 520px; margin: 0 auto; background: white; padding: 24px; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.04);">
          <h2 style="color: #1e40af; margin-top: 0;">🏛️ Bank Complaint AI Desk</h2>
          <p>Hello,</p>
          <p>We received a request to reset your password. Click the secure link below to set a new password:</p>
          <p style="text-align: center; margin: 28px 0;">
            <a href="{reset_link}" style="background-color: #2563eb; color: #ffffff; padding: 12px 26px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
              Reset Password
            </a>
          </p>
          <p style="color: #64748b; font-size: 13px;">This security link is valid for 15 minutes. If you did not request a password reset, please ignore this email.</p>
        </div>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Bank Complaint AI Desk <{smtp_user}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, msg.as_string())
        logger.info(f"Password reset email sent to {to_email}")
    except Exception as exc:
        logger.exception(f"Failed to dispatch reset email via SMTP: {exc}")


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn):
    """Generates a secure password reset token with 15 minutes validity."""
    email = body.email.lower()
    try:
        with pool.connection() as conn:
            user = conn.execute("SELECT id FROM users WHERE email = %s AND is_active = true", [email]).fetchone()
            if not user:
                # Do not disclose if account exists
                return {"message": "If this email is registered, a password reset link has been issued."}

            raw_token, token_hash = generate_reset_token()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

            conn.execute(
                "INSERT INTO password_reset_tokens (email, token_hash, expires_at) "
                "VALUES (%s, %s, %s)",
                [email, token_hash, expires_at],
            )
    except Exception as exc:
        logger.exception("Error creating reset token")
        raise HTTPException(status_code=503, detail="Database is unavailable. Please try again.")

    # Dispatch email
    send_password_reset_email(email, raw_token)
    logger.info(f"Password reset token issued for {email}")
    return {
        "message": "If this email is registered, a password reset link has been issued.",
        "dev_reset_token": raw_token,  # returned for easy testing/demo
    }



@router.post("/reset-password")
def reset_password(body: ResetPasswordIn):
    """Resets user password using the verified reset token."""
    token_hash = hashlib.sha256(body.token.strip().encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    try:
        with pool.connection() as conn:
            token_record = conn.execute(
                "SELECT id, email, expires_at, used FROM password_reset_tokens "
                "WHERE token_hash = %s",
                [token_hash],
            ).fetchone()

            if not token_record or token_record["used"] or token_record["expires_at"] < now:
                raise HTTPException(status_code=400, detail="Reset token is invalid or has expired")

            conn.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                [hash_password(body.new_password), token_record["email"]],
            )
            conn.execute(
                "UPDATE password_reset_tokens SET used = true WHERE id = %s",
                [token_record["id"]],
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error executing password reset")
        raise HTTPException(status_code=503, detail="Database error. Please try again.")

    return {"message": "Password successfully reset. You may now log in with your new password."}


@router.get("/users")
def list_users(admin=Depends(require_role("admin"))):
    try:
        with pool.connection() as conn:
            return conn.execute(
                "SELECT id, email, full_name, role, is_active, created_at "
                "FROM users ORDER BY id"
            ).fetchall()
    except Exception as exc:
        logger.exception("Database error while listing users")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")


@router.put("/users/role")
def update_user_role(body: RoleUpdateIn, admin=Depends(require_role("admin"))):
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "UPDATE users SET role = %s WHERE id = %s RETURNING id, email, role",
                [body.role, body.user_id],
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Database error while updating role")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")
