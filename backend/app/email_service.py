import json
import logging
import os
import smtplib
import ssl
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from app.core.config import settings

logger = logging.getLogger(__name__)


def dispatch_email_transport(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str,
    client_origin: str | None = None,
) -> bool:
    """Dispatches email via Brevo HTTPS API, Vercel Relay, Resend, Maileroo, or falls back to SMTP."""
    # 1. Brevo REST API (HTTPS Port 443 - Recommended for Render & Free Global Delivery)
    brevo_key = (os.getenv("BREVO_API_KEY") or settings.brevo_api_key or "").strip()
    if brevo_key:
        try:
            sender_email = (os.getenv("BREVO_SENDER_EMAIL") or settings.brevo_sender_email or "").strip()
            if not sender_email:
                raise ValueError("BREVO_SENDER_EMAIL is not configured in .env")
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
                headers={
                    "api-key": brevo_key,
                    "Content-Type": "application/json",
                    "User-Agent": "BankComplaintAIDesk/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201, 202):
                    logger.info(f"Email successfully dispatched via Brevo HTTPS API to {to_email}")
                    return True
        except Exception as exc:
            logger.warning(f"Brevo HTTPS dispatch failed for {to_email}: {exc}")

    # 2. Vercel Serverless Function Relay (HTTPS Port 443 -> Vercel Node.js -> Gmail Port 465)
    relay_urls = []
    if client_origin and client_origin.startswith("http") and "localhost" not in client_origin and "127.0.0.1" not in client_origin:
        relay_urls.append(f"{client_origin.rstrip('/')}/api/send-email")

    vercel_url = os.getenv("VERCEL_URL", "").strip()
    if vercel_url:
        if not vercel_url.startswith("http"):
            vercel_url = f"https://{vercel_url}"
        cand = f"{vercel_url.rstrip('/')}/api/send-email"
        if cand not in relay_urls:
            relay_urls.append(cand)

    for relay_url in relay_urls:
        try:
            payload = json.dumps({
                "to_email": to_email,
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }).encode("utf-8")
            req = urllib.request.Request(
                relay_url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status in (200, 201):
                    logger.info(f"Email successfully dispatched via Vercel Serverless Relay ({relay_url}) to {to_email}")
                    return True
        except Exception as exc:
            logger.warning(f"Vercel serverless relay ({relay_url}) failed: {exc}")

    # 3. Resend API (HTTPS Port 443)
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
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Email dispatched via Resend HTTPS API to {to_email}")
                return True
        except Exception as exc:
            logger.error(f"Resend HTTPS dispatch failed: {exc}")

    # 4. Maileroo API (HTTPS Port 443)
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
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201, 202):
                    logger.info(f"Email dispatched via Maileroo HTTPS API to {to_email}")
                    return True
        except Exception as exc:
            logger.warning(f"Maileroo HTTPS dispatch failed: {exc}")

    # 5. Standard SMTP fallback (port 587 or 465)
    smtp_user = (os.getenv("SMTP_USER") or settings.smtp_user or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or settings.smtp_password or "").strip()
    smtp_host = (os.getenv("SMTP_HOST") or settings.smtp_host or "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT") or settings.smtp_port or 587)
    smtp_from = (os.getenv("SMTP_FROM") or settings.smtp_from or smtp_user).strip()

    if not smtp_user or not smtp_password:
        logger.info(f"SMTP/API not fully configured. Skipped email dispatch to {to_email}")
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
        if smtp_port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=15) as srv:
                srv.login(smtp_user, smtp_password)
                srv.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as srv:
                srv.ehlo()
                ctx = ssl.create_default_context()
                srv.starttls(context=ctx)
                srv.ehlo()
                srv.login(smtp_user, smtp_password)
                srv.send_message(msg)
        logger.info(f"Email successfully dispatched via SMTP to {to_email}")
        return True
    except Exception as exc:
        logger.warning(f"SMTP dispatch failed: {exc}")
        return False


def send_complaint_approval_email(
    consumer_email: str,
    complaint_id: int,
    product: str,
    issue: str,
    company: str,
    approver_name: str,
    approver_role: str,
    resolution_text: str,
    client_origin: str | None = None,
) -> bool:
    """Sends official resolution approval notification to the consumer."""
    subject = f"Official Resolution Notice — Bank Complaint #{complaint_id}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b1120; color: #f8fafc; margin: 0; padding: 24px; }}
        .card {{ max-width: 620px; margin: 0 auto; background: #131d33; border: 1px solid #1e293b; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        .header {{ display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 20px; margin-bottom: 24px; }}
        .badge {{ background: #059669; color: #ecfdf5; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 9999px; display: inline-block; }}
        .title {{ font-size: 20px; font-weight: 700; color: #ffffff; margin: 0; }}
        .meta-box {{ background: #0b1120; border-radius: 8px; padding: 16px; margin-bottom: 24px; font-size: 14px; border: 1px solid #1e293b; }}
        .meta-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
        .meta-row:last-child {{ margin-bottom: 0; }}
        .meta-label {{ color: #94a3b8; font-weight: 500; }}
        .meta-value {{ color: #f1f5f9; font-weight: 600; }}
        .resolution-box {{ background: #0f172a; border-left: 4px solid #10b981; border-radius: 6px; padding: 20px; color: #e2e8f0; font-size: 15px; line-height: 1.6; white-space: pre-wrap; margin-bottom: 24px; font-family: 'Courier New', Courier, monospace; }}
        .footer {{ font-size: 12px; color: #64748b; border-top: 1px solid #1e293b; padding-top: 20px; line-height: 1.5; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <div>
            <div class="badge">Official Compliance Resolution</div>
            <h1 class="title" style="margin-top: 8px;">Bank Complaint Resolution Approved</h1>
          </div>
        </div>

        <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">
          Dear Customer,
        </p>
        <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">
          We are writing to inform you that your dispute submitted under <strong>Complaint #{complaint_id}</strong> has been thoroughly investigated and formally approved by bank compliance leadership.
        </p>

        <div class="meta-box">
          <div class="meta-row">
            <span class="meta-label">Complaint Reference:</span>
            <span class="meta-value">#{complaint_id}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Financial Institution:</span>
            <span class="meta-value">{company}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Product / Service:</span>
            <span class="meta-value">{product}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Dispute Issue:</span>
            <span class="meta-value">{issue}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Approved By:</span>
            <span class="meta-value">{approver_name} ({approver_role.title()})</span>
          </div>
        </div>

        <h3 style="color: #f8fafc; font-size: 16px; margin-bottom: 12px;">Official Bank Resolution Letter:</h3>
        <div class="resolution-box">{resolution_text}</div>

        <p style="color: #94a3b8; font-size: 14px; line-height: 1.5;">
          This determination adheres to applicable federal consumer protection laws, including Regulation E (12 CFR Part 1005), Regulation Z (12 CFR Part 1026), and CFPB compliance guidelines.
        </p>

        <div class="footer">
          <p>Bank Complaint AI Desk &bull; Consumer Dispute Compliance Department<br>
          This is an automated notification of formal resolution approval.</p>
        </div>
      </div>
    </body>
    </html>
    """

    text_content = f"""
    Official Bank Resolution Notice — Complaint #{complaint_id}
    
    Dear Customer,
    
    Your dispute (Complaint #{complaint_id}) regarding {product} - {issue} at {company} has been investigated and formally approved by {approver_name} ({approver_role}).
    
    OFFICIAL RESOLUTION:
    --------------------------------------------------
    {resolution_text}
    --------------------------------------------------
    
    This determination adheres to federal banking compliance standards under Regulation E / Z and CFPB guidelines.
    
    Bank Complaint AI Desk - Dispute Compliance Operations
    """

    return dispatch_email_transport(
        to_email=consumer_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        client_origin=client_origin,
    )
