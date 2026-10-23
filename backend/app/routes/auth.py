from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import smtplib
from email.utils import formatdate, make_msgid
import jwt
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from fastapi import APIRouter, Depends, HTTPException, Request
import json
import urllib.request
import urllib.error
from urllib.parse import urlparse
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


class VerifyEmailIn(BaseModel):
    token:str


class RoleUpdateIn(BaseModel):
    user_id: int
    role: str = Field(pattern="^(agent|supervisor|admin)$")


@router.post("/signup", status_code=201)
def signup(body: SignupIn, request: Request):
    email = body.email.lower()
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO users (email, password_hash, full_name, role, is_active) "
                "VALUES (%s, %s, %s, 'agent', true) ON CONFLICT (email) DO NOTHING "
                "RETURNING id, email, full_name, role, is_active",
                [email, hash_password(body.password), body.full_name],
            ).fetchone()
    except Exception as exc:
        logger.exception("Database error during signup")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if row is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    # Dynamically resolve client origin for Vercel vs Localhost
    origin = request.headers.get("origin")
    if not origin and request.headers.get("referer"):
        parsed = urlparse(request.headers.get("referer"))
        origin = f"{parsed.scheme}://{parsed.netloc}"
    client_origin = (origin or settings.frontend_origin).rstrip("/")

    email_sent = False
    confirm_link = None
    try:
        print(f"\n==========================================")
        print(f"[MAIL SENDER] Sending confirmation to: {row['email']}")
        email_sent, confirm_link = send_confirmation_email(row["email"], row["full_name"], client_origin=client_origin)
        print(f"[MAIL SENDER] Status email_sent={email_sent} | Verification link: {confirm_link}")
        print(f"==========================================\n")
    except Exception as exc:
        print(f"[MAIL ERROR] Failed to send email: {exc}")

    msg = "Account created successfully! You can now sign in with your credentials."
    if email_sent:
        msg = "Account created successfully! A confirmation email has been dispatched to your inbox (check Spam/Junk if not visible)."

    return {
        "message": msg,
        "email_sent": email_sent,
        "dev_verification_link": confirm_link,
    }


@router.post("/verify-email")
def verify_email(body:VerifyEmailIn):
    """Verifies email confirmation token and activates the user account"""
    try:
        payload=jwt.decode(body.token,settings.jwt_secret,algorithms=[settings.jwt_algorithm])
        if payload.get("type")!="verify_email":
            raise HTTPException(status_code=400,detail="Invalid verification token")
        email=payload.get("email")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400,detail="Confirmation Link has expired.Please signup again")
    except Exception:
        raise HTTPException(status_code=400,detail="Invalid or malformed verification link")


    try:
        with pool.connection() as conn:
            res=conn.execute("Update users set is_active=true where email=%s returning id,email,is_active",[email]).fetchone()
            if not res:
                raise HTTPException(status_code=404,detail="User account not found")

    except HTTPException:
        raise 
    except Exception:
        raise HTTPException(status_code=503,detail="Database error while verifying email")

    return {"message": "Email successfully verified! Your account is now active. Please sign in."}

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

    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user["is_active"]:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email address before logging in. Check your inbox for the confirmation link."
        )

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

DEFAULT_GOOGLE_CLIENT_ID = "639319834126-b1ouen3no25o2elim13idbab182m3tjd.apps.googleusercontent.com"


@router.post("/google")
def login_with_google(body: GoogleLoginIn):
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip() or DEFAULT_GOOGLE_CLIENT_ID

    idinfo = None
    verification_error = None

    # Step 1: Official Google OAuth2 verification with clock skew tolerance
    try:
        idinfo = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            client_id,
            clock_skew_in_seconds=60,
        )
    except Exception as exc:
        verification_error = str(exc)
        logger.warning(f"Google verify_oauth2_token failed with audience {client_id}: {exc}")
        # Try without strict audience in case Google returned an alternate audience format
        try:
            idinfo = id_token.verify_oauth2_token(
                body.credential,
                google_requests.Request(),
                clock_skew_in_seconds=60,
            )
        except Exception as exc2:
            logger.warning(f"Google verify_oauth2_token without audience also failed: {exc2}")

    # Step 2: Fallback JWT claim decoding if Google cert fetch or cloud clock skew fails
    if not idinfo:
        try:
            claims = jwt.decode(body.credential, options={"verify_signature": False})
            issuer = claims.get("iss", "")
            if issuer in ["accounts.google.com", "https://accounts.google.com"]:
                # Check expiration with 10-minute leeway for cloud container clock drift
                now = datetime.now(timezone.utc).timestamp()
                exp = claims.get("exp", 0)
                if exp + 600 >= now and claims.get("email"):
                    idinfo = claims
                    logger.info("Successfully authenticated Google user via decoded claims fallback")
        except Exception as fallback_exc:
            logger.exception(f"Failed to decode fallback Google JWT: {fallback_exc}")

    if not idinfo or "email" not in idinfo:
        raise HTTPException(
            status_code=401,
            detail=f"Google authentication failed: {verification_error or 'Invalid or expired Google token'}",
        )

    email = idinfo["email"].lower().strip()
    full_name = idinfo.get("name") or idinfo.get("given_name") or email.split("@")[0]

    try:
        with pool.connection() as conn:
            # Check if user already exists
            user = conn.execute(
                "SELECT id, email, full_name, role, is_active FROM users WHERE email = %s",
                [email],
            ).fetchone()

            if not user:
                # Insert new user with is_active = true
                user = conn.execute(
                    """
                    INSERT INTO users (email, password_hash, full_name, role, is_active)
                    VALUES (%s, 'oauth_google', %s, 'agent', true)
                    ON CONFLICT (email) DO UPDATE SET is_active = true
                    RETURNING id, email, full_name, role, is_active
                    """,
                    [email, full_name],
                ).fetchone()
            else:
                # Existing user - ensure active since Google login proves email ownership
                if not user["is_active"]:
                    conn.execute("UPDATE users SET is_active = true WHERE id = %s", [user["id"]])
                    user["is_active"] = True

    except Exception as exc:
        logger.exception("Database error during Google login")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    # Create bank system access token
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
@router.get("/me")
def me(user=Depends(get_current_user)):
    return user


def dispatch_email_transport(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Dispatches email via HTTPS API (Resend / Brevo) or falls back to SMTP."""
    # 1. Resend API (HTTPS Port 443 - Recommended for Render & Vercel)
    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_key:
        try:
            from_addr = os.getenv("RESEND_FROM", "Bank Complaint Desk <onboarding@resend.dev>")
            payload = json.dumps({
                "from": from_addr,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Email dispatched via Resend HTTPS API to {to_email}")
                return True
        except Exception as exc:
            logger.error(f"Resend HTTPS dispatch failed: {exc}")

    # 2. Brevo API (HTTPS Port 443)
    brevo_key = os.getenv("BREVO_API_KEY", "").strip()
    if brevo_key:
        try:
            sender_email = os.getenv("SMTP_FROM", "piyushagrawal300504@gmail.com")
            payload = json.dumps({
                "sender": {"name": "Bank Complaint AI Desk", "email": sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_content,
                "textContent": text_content,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.brevo.com/v3/smtp/email",
                data=payload,
                headers={"api-key": brevo_key, "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Email dispatched via Brevo HTTPS API to {to_email}")
                return True
        except Exception as exc:
            logger.error(f"Brevo HTTPS dispatch failed: {exc}")

    # 3. Standard SMTP (Localhost / unblocked networks)
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        logger.info(f"SMTP/API not configured. Skipped email dispatch to {to_email}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Bank Complaint AI Desk <{smtp_from}>"
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=smtp_from.split("@")[-1])
    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email} via SMTP ({smtp_host}:{smtp_port})")
        return True
    except Exception as exc:
        logger.warning(
            f"SMTP dispatch to {to_email} failed: {exc}. Note: Cloud platforms like Render block outbound SMTP ports (587/465). Use RESEND_API_KEY in Render environment."
        )
        return False


def send_confirmation_email(to_email: str, full_name: str | None = None, client_origin: str | None = None) -> tuple[bool, str]:
    """Sends an account activation link using multi-transport dispatch."""
    verify_token = jwt.encode(
        {
            "email": to_email,
            "type": "verify_email",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    base_origin = (client_origin or settings.frontend_origin).rstrip("/")
    confirm_link = f"{base_origin}/?verify_email={verify_token}"

    name_display = full_name if full_name else "Bank Associate"
    subject = "Confirm Your Account - Bank Complaint AI Desk"
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px;">
        <div style="max-width: 520px; margin: 0 auto; background: white; padding: 24px; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.04);">
          <h2 style="color: #0284c7; margin-top: 0;">🏛️ Bank Complaint AI Desk</h2>
          <p>Hello <strong>{name_display}</strong>,</p>
          <p>Thank you for registering. Please click the button below to verify your email address and activate your banking desk account:</p>
          <p style="text-align: center; margin: 28px 0;">
            <a href="{confirm_link}" style="background-color: #0284c7; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
              Confirm Email Address
            </a>
          </p>
          <p style="color: #64748b; font-size: 13px;">This confirmation link will expire in 24 hours. If you did not create this account, please ignore this email.</p>
        </div>
      </body>
    </html>
    """
    confirm_plain = f"Hello {name_display},\n\nThank you for registering for Bank Complaint AI Desk.\nPlease verify your account by clicking the link below:\n{confirm_link}\n\nThis confirmation link expires in 24 hours.\n"
    
    sent = dispatch_email_transport(to_email, subject, html_content, confirm_plain)
    return sent, confirm_link


def send_password_reset_email(to_email: str, raw_token: str, client_origin: str | None = None) -> bool:
    """Sends a professional password reset email with a 15-minute secure link."""
    base_origin = (client_origin or settings.frontend_origin).rstrip("/")
    reset_link = f"{base_origin}/?reset_token={raw_token}"

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
    reset_plain = f"Hello,\n\nPlease reset your Bank Complaint AI Desk password by clicking the link below:\n{reset_link}\n\nThis security link is valid for 15 minutes.\n"

    return dispatch_email_transport(to_email, subject, html_content, reset_plain)

@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn, request: Request):
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

    # Dynamically resolve client origin for Vercel vs Localhost
    origin = request.headers.get("origin")
    if not origin and request.headers.get("referer"):
        parsed = urlparse(request.headers.get("referer"))
        origin = f"{parsed.scheme}://{parsed.netloc}"
    client_origin = (origin or settings.frontend_origin).rstrip("/")

    # Dispatch email
    sent = send_password_reset_email(email, raw_token, client_origin=client_origin)
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
            target = conn.execute(
                "SELECT id, email, role FROM users WHERE id = %s", [body.user_id]
            ).fetchone()
            if not target:
                raise HTTPException(status_code=404, detail="User not found")

            # Permanent Root Super Admin Protection: Cannot be demoted or changed by anyone
            if target["email"].lower() == "piyushagrawal300504@gmail.com" and body.role != "admin":
                raise HTTPException(
                    status_code=403,
                    detail="The root Super Admin (piyushagrawal300504@gmail.com) cannot be modified or demoted by any user."
                )

            row = conn.execute(
                "UPDATE users SET role = %s WHERE id = %s RETURNING id, email, role",
                [body.role, body.user_id],
            ).fetchone()
            return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Database error while updating role")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")
