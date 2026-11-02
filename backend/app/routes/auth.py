from datetime import datetime, timedelta, timezone
import html
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
from pydantic import BaseModel, EmailStr, Field, field_validator
import re

from app.core.config import settings
from app.db import pool
from app.deps import get_current_user, require_role
from app.security import (
    create_access_token,
    generate_captcha_challenge,
    generate_reset_token,
    hash_password,
    verify_captcha_challenge,
    verify_security_challenge,
    verify_turnstile_token,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

class GoogleLoginIn(BaseModel):
    credential:str




def validate_strong_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(v) > 128:
        raise ValueError("Password must not exceed 128 characters.")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter (A-Z).")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter (a-z).")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one number (0-9).")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("Password must contain at least one special character (e.g. !@#$%^&*).")
    return v


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str | None = None
    full_name: str | None = Field(default=None, max_length=100)
    turnstile_token: str | None = None
    captcha_token: str | None = None
    captcha_answer: str | None = None

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_strong_password(v)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    confirm_password: str | None = None
    turnstile_token: str | None = None
    captcha_token: str | None = None
    captcha_answer: str | None = None


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str | None = None

    @field_validator("new_password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_strong_password(v)


class VerifyEmailIn(BaseModel):
    token:str


class RoleUpdateIn(BaseModel):
    user_id: int
    role: str = Field(pattern="^(agent|supervisor|admin)$")


class RoleUpgradeRequestIn(BaseModel):
    requested_role: str = Field(pattern="^(supervisor|admin)$")
    reason: str | None = Field(default=None, max_length=500)


@router.get("/captcha")
def get_captcha():
    """Generates a math CAPTCHA challenge with an HMAC-SHA256 signed token."""
    return generate_captcha_challenge()


@router.post("/signup", status_code=201)
def signup(body: SignupIn, request: Request):
    # Verify Security (Cloudflare Turnstile with CAPTCHA fallback)
    client_ip = request.client.host if request.client else None
    is_valid, err_msg = verify_security_challenge(
        turnstile_token=body.turnstile_token,
        captcha_token=body.captcha_token,
        captcha_answer=body.captcha_answer,
        client_ip=client_ip,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    if body.confirm_password and body.confirm_password != body.password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    email = body.email.lower().strip()
    # ALL signups via public registration are assigned role 'agent' and is_active = False pending email verification
    init_role = "agent"
    init_active = False
    supervisor_id = None
    try:
        with pool.connection() as conn:
            if init_role == "agent":
                sup_row = conn.execute(
                    """
                    SELECT s.id
                    FROM users s
                    LEFT JOIN users a ON a.supervisor_id = s.id AND a.role = 'agent' AND a.is_active = true
                    WHERE s.role = 'supervisor' AND s.is_active = true
                    GROUP BY s.id
                    HAVING COUNT(a.id) < 50
                    ORDER BY COUNT(a.id) ASC, s.id ASC
                    LIMIT 1;
                    """
                ).fetchone()
                if sup_row:
                    supervisor_id = sup_row["id"]

            row = conn.execute(
                "INSERT INTO users (email, password_hash, full_name, role, is_active, supervisor_id) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING "
                "RETURNING id, email, full_name, role, is_active, supervisor_id",
                [email, hash_password(body.password), body.full_name, init_role, init_active, supervisor_id],
            ).fetchone()
    except Exception as exc:
        logger.exception("Database error during signup")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if row is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    client_origin = settings.get_safe_frontend_origin(request)

    email_sent = False
    try:
        email_sent, _ = send_confirmation_email(row["email"], row["full_name"], client_origin=client_origin)
    except Exception as exc:
        logger.warning(f"Failed to dispatch account confirmation email: {exc}")

    msg = "Account created successfully! Please verify your email before logging in."
    if email_sent:
        msg = "Account created successfully! A confirmation email has been dispatched to your inbox."

    return {
        "message": msg,
        "email_sent": email_sent,
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
def login(body: LoginIn, request: Request):
    # Verify Security (Cloudflare Turnstile with CAPTCHA fallback)
    client_ip = request.client.host if request.client else None
    is_valid, err_msg = verify_security_challenge(
        turnstile_token=body.turnstile_token,
        captcha_token=body.captcha_token,
        captcha_answer=body.captcha_answer,
        client_ip=client_ip,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    if body.confirm_password and body.confirm_password != body.password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

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

    # Enforce permanent super admin rights
    super_admin = (settings.super_admin_email or "piyushagrawal300504@gmail.com").strip().lower()
    if email == super_admin or email == "piyushagrawal300504@gmail.com":
        user["role"] = "admin"
        user["is_active"] = True
        try:
            with pool.connection() as fix_conn:
                fix_conn.execute("UPDATE users SET role = 'admin', is_active = true WHERE id = %s", [user["id"]])
        except Exception:
            pass

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

@router.post("/google")
def login_with_google(body: GoogleLoginIn):
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or settings.google_client_id or "").strip()
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured on the server. Please set GOOGLE_CLIENT_ID in backend/.env",
        )

    # Strictly require verified cryptographic signature from Google
    try:
        idinfo = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            client_id,
            clock_skew_in_seconds=10,
        )
    except Exception as exc:
        logger.warning(f"Google verify_oauth2_token signature verification failed: {exc}")
        raise HTTPException(
            status_code=401,
            detail="Google authentication failed: Invalid or expired token signature.",
        )

    if not idinfo or "email" not in idinfo:
        raise HTTPException(
            status_code=401,
            detail="Google authentication failed: Token missing email identity claim.",
        )

    email = idinfo["email"].lower().strip()
    full_name = idinfo.get("name") or idinfo.get("given_name") or email.split("@")[0]

    try:
        with pool.connection() as conn:
            user = conn.execute(
                "SELECT id, email, full_name, role, is_active FROM users WHERE email = %s",
                [email],
            ).fetchone()

            if user:
                # If an administrator explicitly deactivated this account, Google OAuth cannot bypass the ban
                if not user["is_active"]:
                    raise HTTPException(
                        status_code=403,
                        detail="Your account has been deactivated by an Administrator. Please contact support.",
                    )
            else:
                # New Google users are created strictly with standard 'agent' role
                user = conn.execute(
                    """
                    INSERT INTO users (email, password_hash, full_name, role, is_active)
                    VALUES (%s, 'oauth_google', %s, 'agent', true)
                    ON CONFLICT (email) DO NOTHING
                    RETURNING id, email, full_name, role, is_active
                    """,
                    [email, full_name],
                ).fetchone()

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


def dispatch_email_transport(to_email: str, subject: str, html_content: str, text_content: str, client_origin: str | None = None) -> bool:
    """Dispatches email via Brevo HTTPS API, Vercel Relay, Resend, or falls back to SMTP."""
    # 1. Brevo REST API (HTTPS Port 443 - Recommended for Render & Free Global Delivery)
    brevo_key = (os.getenv("BREVO_API_KEY") or settings.brevo_api_key or "").strip()
    if brevo_key:
        try:
            sender_email = (os.getenv("BREVO_SENDER_EMAIL") or settings.brevo_sender_email or "").strip()
            if not sender_email:
                raise ValueError("BREVO_SENDER_EMAIL is not configured in .env")
            sender_name = (os.getenv("BREVO_SENDER_NAME") or getattr(settings, "brevo_sender_name", None) or "Bank Complaint AI Desk").strip()
            payload = json.dumps({
                "sender": {"name": sender_name, "email": sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_content,
                "textContent": text_content,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.brevo.com/v3/smtp/email",
                data=payload,
                headers={"api-key": brevo_key, "Content-Type": "application/json", "User-Agent": "BankComplaintAIDesk/1.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201, 202):
                    logger.info(f"Email successfully dispatched via Brevo HTTPS API to {to_email}")
                    return True
        except Exception as exc:
            logger.warning(f"Brevo HTTPS dispatch failed for {to_email}: {exc}")

    # Direct secure transports: Brevo REST API -> Resend API -> SMTP
    # 1. Resend API (HTTPS Port 443 - Recommended for Render & Vercel)
    resend_key = (os.getenv("RESEND_API_KEY") or settings.resend_api_key or "").strip()
    if resend_key:
        try:
            from_addr = (os.getenv("RESEND_FROM") or settings.resend_from or "Bank Complaint Desk <onboarding@resend.dev>").strip()
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

    # 2. Maileroo API (HTTPS Port 443)
    maileroo_key = (os.getenv("MAILEROO_API_KEY") or settings.maileroo_api_key or "").strip()
    if maileroo_key:
        try:
            sender_email = (os.getenv("MAILEROO_FROM") or settings.maileroo_from or os.getenv("SMTP_FROM") or settings.smtp_from or "").strip()
            if not sender_email:
                raise ValueError("Sender email is not configured for Maileroo in .env")
            payload = json.dumps({
                "from": {"email": sender_email, "name": "Bank Complaint AI Desk"},
                "to": [{"email": to_email, "name": "Bank User"}],
                "subject": subject,
                "html": html_content,
                "plain": text_content,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.maileroo.com/v1/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {maileroo_key}",
                    "X-API-Key": maileroo_key,
                    "Content-Type": "application/json",
                    "User-Agent": "BankComplaintAIDesk/1.0",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201, 202):
                    logger.info(f"Email dispatched via Maileroo HTTPS API to {to_email}")
                    return True
        except Exception as exc:
            logger.warning(f"Maileroo HTTPS dispatch failed: {exc}")



    # 3. Standard SMTP (Localhost / unblocked networks)
    smtp_user = (os.getenv("SMTP_USER") or settings.smtp_user or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or settings.smtp_password or "").strip()
    smtp_host = (os.getenv("SMTP_HOST") or settings.smtp_host or "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT") or settings.smtp_port or 587)
    smtp_from = (os.getenv("SMTP_FROM") or settings.smtp_from or smtp_user).strip()

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

    # Try SSL 465 first
    try:
        with smtplib.SMTP_SSL(smtp_host, 465, timeout=6) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email} via SMTP_SSL ({smtp_host}:465)")
        return True
    except Exception as ssl_exc:
        logger.warning(f"SMTP_SSL 465 failed: {ssl_exc}. Attempting STARTTLS 587...")

    # Try STARTTLS 587 fallback
    try:
        with smtplib.SMTP(smtp_host, 587, timeout=6) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email} via SMTP STARTTLS ({smtp_host}:587)")
        return True
    except Exception as exc:
        logger.warning(
            f"SMTP dispatch to {to_email} failed: {exc}. Note: Cloud platforms like Render block outbound SMTP ports (587/465)."
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

    name_display = html.escape(full_name) if full_name else "Bank Associate"
    subject = "Confirm Your Account - Bank Complaint AI Desk"
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px;">
        <div style="max-width: 520px; margin: 0 auto; background: white; padding: 24px; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.04);">
          <h2 style="color: #0284c7; margin-top: 0;">Bank Complaint AI Desk</h2>
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
    
    sent = dispatch_email_transport(to_email, subject, html_content, confirm_plain, client_origin=client_origin)
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
          <h2 style="color: #1e40af; margin-top: 0;">Bank Complaint AI Desk</h2>
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

    return dispatch_email_transport(to_email, subject, html_content, reset_plain, client_origin=client_origin)

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

    client_origin = settings.get_safe_frontend_origin(request)

    # Dispatch email
    sent = send_password_reset_email(email, raw_token, client_origin=client_origin)
    logger.info(f"Password reset token issued for {email}")
    return {
        "message": "If this email is registered, a password reset link has been issued.",
    }



@router.post("/reset-password")
def reset_password(body: ResetPasswordIn):
    """Resets user password using the verified reset token."""
    if body.confirm_password and body.confirm_password != body.new_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
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
            rows = conn.execute(
                """
                SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at, u.supervisor_id,
                       s.full_name AS supervisor_name, s.email AS supervisor_email
                FROM users u
                LEFT JOIN users s ON u.supervisor_id = s.id
                ORDER BY u.id
                """
            ).fetchall()
            super_admin = (settings.super_admin_email or "piyushagrawal300504@gmail.com").strip().lower()
            for r in rows:
                if r["email"].lower() == super_admin or r["email"].lower() == "piyushagrawal300504@gmail.com":
                    r["role"] = "admin"
                    r["is_active"] = True
            return rows
    except Exception as exc:
        logger.exception("Database error while listing users")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")


class AssignSupervisorIn(BaseModel):
    agent_id: int
    supervisor_id: int | None = None


@router.get("/supervisors")
def list_supervisors(user=Depends(get_current_user)):
    """Returns active supervisors with their assigned agent counts and capacity limits (max 50)."""
    sql = """
        SELECT s.id, s.full_name, s.email, COUNT(a.id) AS assigned_agent_count,
               50 AS max_capacity, (50 - COUNT(a.id)) AS available_slots
        FROM users s
        LEFT JOIN users a ON a.supervisor_id = s.id AND a.role = 'agent' AND a.is_active = true
        WHERE s.role = 'supervisor' AND s.is_active = true
        GROUP BY s.id, s.full_name, s.email
        ORDER BY s.full_name ASC;
    """
    try:
        with pool.connection() as conn:
            return conn.execute(sql).fetchall()
    except Exception as exc:
        logger.exception("Database error while listing supervisors")
        raise HTTPException(status_code=500, detail="Failed to fetch supervisors")


@router.put("/users/supervisor")
def assign_agent_supervisor(body: AssignSupervisorIn, admin=Depends(require_role("admin"))):
    """Admin assigns or reassigns an agent under a supervisor (enforcing max 50 agents per supervisor)."""
    try:
        with pool.connection() as conn:
            agent = conn.execute("SELECT id, role, full_name, email FROM users WHERE id = %s", [body.agent_id]).fetchone()
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            if agent["role"] != "agent":
                raise HTTPException(status_code=400, detail="Only users with 'agent' role can be assigned under a supervisor.")

            if body.supervisor_id is not None:
                supervisor = conn.execute(
                    "SELECT id, role, full_name, is_active FROM users WHERE id = %s",
                    [body.supervisor_id]
                ).fetchone()
                if not supervisor:
                    raise HTTPException(status_code=404, detail="Supervisor not found")
                if supervisor["role"] != "supervisor":
                    raise HTTPException(status_code=400, detail="Target user must have the 'supervisor' role.")
                if not supervisor["is_active"]:
                    raise HTTPException(status_code=400, detail="Cannot assign an agent to an inactive supervisor.")

                # Enforce max 50 agents limit
                count_row = conn.execute(
                    "SELECT COUNT(*) AS n FROM users WHERE supervisor_id = %s AND role = 'agent' AND id != %s AND is_active = true",
                    [body.supervisor_id, body.agent_id]
                ).fetchone()
                if count_row and count_row["n"] >= 50:
                    raise HTTPException(status_code=400, detail="Supervisor has reached the maximum capacity of 50 agents.")

            conn.execute("UPDATE users SET supervisor_id = %s WHERE id = %s", [body.supervisor_id, body.agent_id])
            return {
                "success": True,
                "message": f"Supervisor updated for agent {agent['full_name'] or agent['email']}."
            }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Database error assigning supervisor")
        raise HTTPException(status_code=503, detail="Database error while assigning supervisor.")


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
            super_admin = (settings.super_admin_email or "piyushagrawal300504@gmail.com").strip().lower()
            target_email = target["email"].lower()
            if target_email == super_admin or target_email == "piyushagrawal300504@gmail.com":
                raise HTTPException(
                    status_code=403,
                    detail=f"The root Super Admin ({target['email']}) is permanent and cannot be modified or demoted by any user."
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


@router.post("/role-upgrade/request")
def request_role_upgrade(request: Request, body: RoleUpgradeRequestIn, user=Depends(get_current_user)):
    """Allows an Agent or Supervisor to request a formal promotion to Supervisor or Admin."""
    user_id = user["id"]
    current_role = (user.get("role") or "agent").lower()
    target_role = body.requested_role.lower()

    if current_role == "admin":
        raise HTTPException(status_code=400, detail="You already hold the highest administrative role (Admin).")

    if current_role == "supervisor" and target_role != "admin":
        raise HTTPException(status_code=400, detail="As a Supervisor, you can only request promotion to Admin.")

    if current_role == target_role:
        raise HTTPException(status_code=400, detail=f"You are already assigned as {current_role.capitalize()}.")

    try:
        with pool.connection() as conn:
            existing = conn.execute(
                "SELECT id, to_role, status FROM role_upgrade_requests WHERE user_id = %s AND status = 'pending'",
                [user_id]
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE role_upgrade_requests SET from_role = %s, to_role = %s, reason = %s, created_at = now() WHERE id = %s",
                    [current_role, target_role, body.reason, existing["id"]]
                )
                req_id = existing["id"]
            else:
                row = conn.execute(
                    "INSERT INTO role_upgrade_requests (user_id, from_role, to_role, reason, status) "
                    "VALUES (%s, %s, %s, %s, 'pending') RETURNING id",
                    [user_id, current_role, target_role, body.reason]
                ).fetchone()
                req_id = row["id"]
    except Exception:
        logger.exception("Database error while creating role upgrade request")
        raise HTTPException(status_code=503, detail="Database error. Please try again.")

    # Send non-blocking notification to Super Admin with clickable portal link
    try:
        user_name = user.get("full_name") or user.get("email")
        user_email = user.get("email") or ""
        super_admin = (settings.super_admin_email or "piyushagrawal300504@gmail.com").strip().lower()
        subject = f"Action Required: Role Upgrade Request from {user_name} ({target_role.upper()})"
        
        client_origin = settings.get_safe_frontend_origin(request)
        portal_url = client_origin

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 24px 12px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #0f172a;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-top: 5px solid #1e40af; border-radius: 12px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05); overflow: hidden;">
    
    <!-- Header -->
    <div style="padding: 24px 30px; border-bottom: 1px solid #f1f5f9;">
      <span style="display: inline-block; background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 10px; border-radius: 9999px; margin-bottom: 10px;">
        Action Required: User Role Elevation
      </span>
      <h2 style="margin: 0; font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">
        Role Upgrade Request Awaiting Review
      </h2>
      <p style="margin: 6px 0 0; font-size: 13px; color: #64748b;">
        Bank Complaint AI Desk &bull; Enterprise Governance &amp; RBAC Access Control
      </p>
    </div>

    <!-- Body Details -->
    <div style="padding: 24px 30px;">
      <p style="margin: 0 0 16px; font-size: 15px; color: #334155; line-height: 1.6;">
        Hello Administrator,
      </p>
      <p style="margin: 0 0 18px; font-size: 15px; color: #334155; line-height: 1.6;">
        A team member has formally requested elevated role permissions in the bank dispute desk:
      </p>

      <!-- Details Card -->
      <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr>
            <td style="padding: 6px 0; color: #64748b; width: 35%;">Applicant Name:</td>
            <td style="padding: 6px 0; color: #0f172a; font-weight: 700;">{html.escape(user_name)}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Email Address:</td>
            <td style="padding: 6px 0; color: #0f172a; font-weight: 600;">{html.escape(user_email)}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Current Role:</td>
            <td style="padding: 6px 0; color: #475569; font-weight: 600; text-transform: uppercase;">{current_role.upper()}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Requested Role:</td>
            <td style="padding: 6px 0;">
              <span style="background-color: #dbeafe; color: #1e40af; font-weight: 700; padding: 2px 8px; border-radius: 4px; font-size: 13px; text-transform: uppercase;">
                {target_role.upper()}
              </span>
            </td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b; vertical-align: top;">Business Reason:</td>
            <td style="padding: 6px 0; color: #1e293b; font-style: italic; line-height: 1.4;">
              "{html.escape(body.reason or 'No specific justification provided')}"
            </td>
          </tr>
        </table>
      </div>

      <!-- Action Button / Link -->
      <div style="text-align: center; margin: 30px 0 20px;">
        <a href="{portal_url}" style="display: inline-block; background-color: #1e40af; color: #ffffff; font-weight: 700; font-size: 15px; text-decoration: none; padding: 13px 32px; border-radius: 8px; box-shadow: 0 4px 14px rgba(30, 64, 175, 0.3);">
          👉 Log in to Review Request
        </a>
      </div>

      <p style="text-align: center; font-size: 13px; color: #64748b; margin: 0;">
        Or access directly via: <a href="{portal_url}" style="color: #2563eb; text-decoration: underline; font-weight: 500;">{portal_url}</a>
      </p>
    </div>

    <!-- Footer -->
    <div style="background-color: #0f172a; padding: 16px 30px; text-align: center; font-size: 11px; color: #94a3b8; line-height: 1.5;">
      Bank Complaint AI Desk &bull; Systems &amp; Compliance Management<br>
      This is an internal governance alert for designated System Administrators.
    </div>

  </div>
</body>
</html>"""

        plain_content = f"""BANK COMPLAINT AI DESK — ROLE UPGRADE REQUEST
================================================================================
Applicant: {user_name} ({user_email})
Current Role: {current_role.upper()}
Requested Role: {target_role.upper()}
Reason: {body.reason or 'No reason provided'}

To review and approve or reject this request, please log in below:
{portal_url}
================================================================================
"""
        dispatch_email_transport(super_admin, subject, html_content, plain_content, client_origin=client_origin)
    except Exception as email_err:
        logger.exception(f"Could not dispatch email notification for role upgrade: {email_err}")

    return {
        "message": f"Role upgrade request for {target_role.upper()} submitted successfully! It is now pending Admin approval.",
        "request_id": req_id,
        "to_role": target_role,
        "status": "pending"
    }


@router.get("/role-upgrade/my-status")
def get_my_role_upgrade_status(user=Depends(get_current_user)):
    """Retrieves current pending or recent upgrade request for the logged-in user."""
    user_id = user["id"]
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT id, from_role, to_role, reason, status, created_at, reviewed_at "
                "FROM role_upgrade_requests WHERE user_id = %s ORDER BY id DESC LIMIT 1",
                [user_id]
            ).fetchone()
            if not row:
                return {"has_pending": False, "request": None}
            return {
                "has_pending": row["status"] == "pending",
                "request": {
                    "id": row["id"],
                    "from_role": row["from_role"],
                    "to_role": row["to_role"],
                    "reason": row["reason"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "reviewed_at": row["reviewed_at"].isoformat() if row.get("reviewed_at") else None,
                }
            }
    except Exception:
        logger.exception("Database error while checking role upgrade status")
        return {"has_pending": False, "request": None}


@router.get("/role-upgrade/pending")
def list_pending_role_upgrades(admin=Depends(require_role("admin"))):
    """Admin endpoint to view all pending promotion requests across the bank desk."""
    try:
        with pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT r.id, r.user_id, r.from_role, r.to_role, r.reason, r.status, r.created_at,
                       u.email, u.full_name
                FROM role_upgrade_requests r
                JOIN users u ON u.id = r.user_id
                WHERE r.status = 'pending'
                ORDER BY r.created_at ASC
                """
            ).fetchall()
            return rows
    except Exception:
        logger.exception("Database error while listing pending role upgrades")
        raise HTTPException(status_code=503, detail="Database error while listing pending requests.")


@router.post("/role-upgrade/{request_id}/approve")
def approve_role_upgrade(request: Request, request_id: int, admin=Depends(require_role("admin"))):
    """Admin endpoint to formally approve a role upgrade request and update user permissions."""
    admin_id = admin["id"]
    try:
        with pool.connection() as conn:
            req = conn.execute(
                "SELECT id, user_id, to_role, status FROM role_upgrade_requests WHERE id = %s",
                [request_id]
            ).fetchone()
            if not req:
                raise HTTPException(status_code=404, detail="Role upgrade request not found.")
            if req["status"] != "pending":
                raise HTTPException(status_code=400, detail=f"Request has already been {req['status']}.")

            target_user_id = req["user_id"]
            new_role = req["to_role"]

            # Update the user's role in the database
            conn.execute("UPDATE users SET role = %s WHERE id = %s", [new_role, target_user_id])
            # Mark request as approved
            conn.execute(
                "UPDATE role_upgrade_requests SET status = 'approved', reviewed_at = now(), reviewed_by_id = %s WHERE id = %s",
                [admin_id, request_id]
            )
            user_info = conn.execute(
                "SELECT id, email, full_name, role FROM users WHERE id = %s",
                [target_user_id]
            ).fetchone()

            # Dispatch congratulatory email notification to user asynchronously (never blocks the HTTP response)
            if user_info and user_info.get("email"):
                target_email = user_info["email"]
                user_name = user_info.get("full_name") or target_email.split("@")[0]
                admin_name = admin.get("full_name") or admin.get("email", "Admin")
                subject = f"Role Upgrade Approved: Welcome to {new_role.upper()}"
                portal_url = settings.get_safe_frontend_origin(request)
                html_content = f"""
                <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
                    <div style="background: #1e3a8a; padding: 16px; border-radius: 6px; text-align: center; margin-bottom: 20px;">
                        <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Bank Complaint AI Desk</h2>
                    </div>
                    <h3 style="color: #0f172a; margin-top: 0;">Congratulations, {html.escape(user_name)}!</h3>
                    <p style="color: #334155; font-size: 15px; line-height: 1.5;">
                        Your request to be promoted to <strong>{html.escape(new_role.upper())}</strong> has been reviewed and <strong style="color: #16a34a;">APPROVED</strong> by administrator ({html.escape(admin_name)}).
                    </p>
                    <div style="background: #f0fdf4; border: 1px solid #bbf7d0; padding: 14px; border-radius: 6px; margin: 18px 0;">
                        <p style="margin: 0; color: #166534; font-size: 14px;">
                            <strong>New Role:</strong> {html.escape(new_role.upper())}<br/>
                            <strong>Status:</strong> Active immediately
                        </p>
                    </div>
                    <p style="color: #475569; font-size: 14px;">
                        Your elevated permissions are active right now. Next time you view your desk, you will have full access to your new tools and workflows.
                    </p>
                    <div style="text-align: center; margin: 24px 0 16px;">
                        <a href="{portal_url}" style="display: inline-block; background-color: #16a34a; color: #ffffff; font-weight: 700; font-size: 14px; text-decoration: none; padding: 12px 28px; border-radius: 8px;">
                            🚀 Log in to Your Account
                        </a>
                    </div>
                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
                    <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                        Automated notification from Bank Complaint AI Desk Compliance & Governance Engine.
                    </p>
                </div>
                """
                text_content = f"Congratulations {user_name}! Your request to become {new_role.upper()} has been approved by the administrator."
                try:
                    import threading
                    threading.Thread(
                        target=dispatch_email_transport,
                        args=(target_email, subject, html_content, text_content),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.warning(f"Could not dispatch async role upgrade approval email: {e}")

            return {
                "message": f"Successfully approved! User is now promoted to {new_role.upper()}.",
                "user": user_info
            }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error while approving role upgrade")
        raise HTTPException(status_code=503, detail="Database error while approving request.")


@router.post("/role-upgrade/{request_id}/reject")
def reject_role_upgrade(request_id: int, admin=Depends(require_role("admin"))):
    """Admin endpoint to formally decline a role upgrade request."""
    admin_id = admin["id"]
    try:
        with pool.connection() as conn:
            req = conn.execute(
                "SELECT id, user_id, to_role, status FROM role_upgrade_requests WHERE id = %s",
                [request_id]
            ).fetchone()
            if not req:
                raise HTTPException(status_code=404, detail="Role upgrade request not found.")
            if req["status"] != "pending":
                raise HTTPException(status_code=400, detail=f"Request has already been {req['status']}.")

            target_user_id = req["user_id"]
            to_role = req["to_role"]

            conn.execute(
                "UPDATE role_upgrade_requests SET status = 'rejected', reviewed_at = now(), reviewed_by_id = %s WHERE id = %s",
                [admin_id, request_id]
            )

            # Dispatch notification email to user
            user_info = conn.execute(
                "SELECT id, email, full_name FROM users WHERE id = %s",
                [target_user_id]
            ).fetchone()
            if user_info and user_info.get("email"):
                target_email = user_info["email"]
                user_name = user_info.get("full_name") or target_email.split("@")[0]
                subject = f"Role Upgrade Request Update - Bank Complaint AI Desk"
                html_content = f"""
                <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
                    <div style="background: #1e3a8a; padding: 16px; border-radius: 6px; text-align: center; margin-bottom: 20px;">
                        <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Bank Complaint AI Desk</h2>
                    </div>
                    <h3 style="color: #0f172a; margin-top: 0;">Hello {user_name},</h3>
                    <p style="color: #334155; font-size: 15px; line-height: 1.5;">
                        Your request to be promoted to <strong>{to_role.upper()}</strong> was reviewed and has not been approved at this time.
                    </p>
                    <p style="color: #475569; font-size: 14px;">
                        Your account continues with its current permissions. If you have questions regarding this decision, please consult your desk administrator.
                    </p>
                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
                    <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                        Automated notification from Bank Complaint AI Desk Compliance & Governance Engine.
                    </p>
                </div>
                """
                text_content = f"Hello {user_name}, your request to become {to_role.upper()} was reviewed and not approved at this time."
                try:
                    import threading
                    threading.Thread(
                        target=dispatch_email_transport,
                        args=(target_email, subject, html_content, text_content),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.warning(f"Could not dispatch async role upgrade rejection email: {e}")

            return {"message": "Role upgrade request has been rejected."}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error while rejecting role upgrade")
        raise HTTPException(status_code=503, detail="Database error while rejecting request.")
