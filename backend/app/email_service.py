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
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; color: #0f172a; margin: 0; padding: 24px 12px; }}
        .card {{ max-width: 640px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(15, 23, 42, 0.06); }}
        .header-bar {{ background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%); padding: 24px 32px; color: #ffffff; }}
        .header-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        .bank-brand {{ font-size: 18px; font-weight: 700; letter-spacing: -0.3px; color: #ffffff; }}
        .badge {{ background: #10b981; color: #ffffff; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.5px; display: inline-block; }}
        .header-title {{ font-size: 21px; font-weight: 700; margin: 0; color: #ffffff; line-height: 1.3; }}
        .content-body {{ padding: 32px; }}
        .greeting {{ font-size: 15px; color: #334155; line-height: 1.6; margin: 0 0 16px; }}
        .meta-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px 20px; margin: 24px 0; font-size: 13.5px; }}
        .meta-row {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f1f5f9; }}
        .meta-row:last-child {{ border-bottom: none; }}
        .meta-label {{ color: #64748b; font-weight: 500; }}
        .meta-value {{ color: #0f172a; font-weight: 600; text-align: right; }}
        .section-label {{ font-size: 14px; font-weight: 700; color: #1e293b; text-transform: uppercase; letter-spacing: 0.5px; margin: 24px 0 10px; }}
        .resolution-box {{ background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #2563eb; border-radius: 6px; padding: 20px; color: #1e293b; font-size: 14px; line-height: 1.7; white-space: pre-wrap; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }}
        .regulatory-note {{ font-size: 12.5px; color: #64748b; line-height: 1.6; background: #eff6ff; border-radius: 6px; padding: 12px 16px; margin: 24px 0 0; border: 1px solid #dbeafe; }}
        .footer {{ font-size: 12px; color: #94a3b8; border-top: 1px solid #f1f5f9; padding: 20px 32px; background: #fafafa; text-align: center; line-height: 1.5; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header-bar">
          <div class="header-top">
            <span class="bank-brand">{company}</span>
            <span class="badge">&#10003; Approved &amp; Verified</span>
          </div>
          <h1 class="header-title">Official Dispute Resolution Notice</h1>
        </div>

        <div class="content-body">
          <p class="greeting">Dear Customer,</p>
          <p class="greeting">
            We are writing to provide you with the formal determination regarding your dispute registered under <strong>Complaint #{complaint_id}</strong>. This matter has undergone thorough investigation and regulatory review by compliance leadership.
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
              <span class="meta-label">Product / Vertical:</span>
              <span class="meta-value">{product}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Dispute Issue:</span>
              <span class="meta-value">{issue}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Compliance Approver:</span>
              <span class="meta-value">{approver_name} ({approver_role.title()})</span>
            </div>
          </div>

          <div class="section-label">Official Determination &amp; Letter:</div>
          <div class="resolution-box">{resolution_text}</div>

          <div class="regulatory-note">
            <strong>Regulatory Compliance Notice:</strong> This determination adheres to federal financial consumer protection regulations, including Regulation E (12 CFR Part 1005), Regulation Z (12 CFR Part 1026), and CFPB examination standards.
          </div>
        </div>

        <div class="footer">
          <p style="margin: 0;">Bank Complaint AI Desk &bull; Consumer Dispute Compliance Department</p>
          <p style="margin: 4px 0 0;">This is an automated notification of formal dispute resolution. All rights reserved.</p>
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



def send_supervisor_approval_request_email(
    to_email: str,
    supervisor_name: str,
    complaint_id: int,
    company: str,
    product: str,
    issue: str,
    agent_name: str,
    response_draft: str,
    client_origin: str | None = None,
) -> bool:
    """Dispatches a notification email to a supervisor when an agent requests resolution approval."""
    subject = f"Action Required: Complaint #{complaint_id} Pending Review ({company})"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #0f172a; margin: 0; padding: 24px; }}
        .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}
        .badge {{ background: #eff6ff; color: #1d4ed8; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; display: inline-block; text-transform: uppercase; border: 1px solid #bfdbfe; margin-bottom: 12px; }}
        .title {{ font-size: 20px; font-weight: 700; color: #0f172a; margin: 0 0 16px; }}
        .meta-box {{ background: #f8fafc; border-radius: 8px; padding: 16px; margin: 20px 0; font-size: 14px; border: 1px solid #e2e8f0; }}
        .meta-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
        .meta-row:last-child {{ margin-bottom: 0; }}
        .meta-label {{ color: #64748b; font-weight: 500; }}
        .meta-value {{ color: #0f172a; font-weight: 600; }}
        .draft-preview {{ background: #f1f5f9; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 16px; color: #1e293b; font-size: 14px; line-height: 1.6; white-space: pre-wrap; margin: 20px 0; }}
        .footer {{ font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 24px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <span class="badge">Dispute Review Requested</span>
        <h1 class="title">Resolution Draft Awaiting Approval</h1>
        <p>Dear {supervisor_name or 'Supervisor'},</p>
        <p>Agent <strong>{agent_name}</strong> has submitted an official resolution draft for Complaint <strong>#{complaint_id}</strong>. Please log into the Bank Complaint AI Desk to review, customize if necessary, and formally approve the response.</p>
        
        <div class="meta-box">
          <div class="meta-row">
            <span class="meta-label">Complaint ID:</span>
            <span class="meta-value">#{complaint_id}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Bank / Institution:</span>
            <span class="meta-value">{company}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Product:</span>
            <span class="meta-value">{product}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Dispute Issue:</span>
            <span class="meta-value">{issue}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Submitted By:</span>
            <span class="meta-value">{agent_name}</span>
          </div>
        </div>

        <p style="font-weight: 600; font-size: 14px; margin-bottom: 6px;">Draft Resolution Letter Preview:</p>
        <div class="draft-preview">{response_draft[:800]}...</div>

        <p style="font-size: 14px; color: #475569;">Prompt approval ensures timely delivery to the consumer within mandatory regulatory windows (e.g. Regulation E / Z).</p>

        <div class="footer">
          <p>Bank Complaint AI Desk &bull; Regulatory Compliance Operations</p>
        </div>
      </div>
    </body>
    </html>
    """

    text_content = f"""
    Dispute Review Request — Complaint #{complaint_id}
    
    Dear {supervisor_name or 'Supervisor'},
    
    Agent {agent_name} has submitted an official resolution draft for Complaint #{complaint_id} ({company} - {product}) awaiting your review and approval.
    
    Dispute Issue: {issue}
    
    Draft Preview:
    --------------------------------------------------
    {response_draft[:600]}...
    --------------------------------------------------
    
    Please sign into the Bank Complaint AI Desk to review and formally approve this case.
    
    Bank Complaint AI Desk - Regulatory Compliance Operations
    """

    return dispatch_email_transport(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        client_origin=client_origin,
    )



def send_agent_rejection_notification_email(
    to_email: str,
    agent_name: str,
    complaint_id: int,
    company: str,
    supervisor_name: str,
    reason: str,
    client_origin: str | None = None,
) -> bool:
    """Dispatches a notification email to an agent when a supervisor requests changes / rejects a draft."""
    subject = f"Revisions Required: Complaint #{complaint_id} ({company})"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #0f172a; margin: 0; padding: 24px; }}
        .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #fed7aa; border-radius: 12px; padding: 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}
        .badge {{ background: #fff7ed; color: #c2410c; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; display: inline-block; text-transform: uppercase; border: 1px solid #fdba74; margin-bottom: 12px; }}
        .title {{ font-size: 20px; font-weight: 700; color: #9a3412; margin: 0 0 16px; }}
        .feedback-box {{ background: #fff7ed; border-left: 4px solid #ea580c; border-radius: 6px; padding: 16px; color: #7c2d12; font-size: 14px; line-height: 1.6; white-space: pre-wrap; margin: 20px 0; }}
        .footer {{ font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 24px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <span class="badge">Revisions Requested</span>
        <h1 class="title">Resolution Draft Requires Update</h1>
        <p>Dear {agent_name or 'Agent'},</p>
        <p>Supervisor <strong>{supervisor_name}</strong> has reviewed your resolution draft for Complaint <strong>#{complaint_id}</strong> ({company}) and requested modifications before it can be approved for customer dispatch.</p>
        
        <p style="font-weight: 600; font-size: 14px; margin-bottom: 6px;">Supervisor Feedback & Instructions:</p>
        <div class="feedback-box">{reason}</div>

        <p style="font-size: 14px; color: #475569;">Please log into the Bank Complaint AI Desk, update your draft according to the feedback above, and re-submit it for approval.</p>

        <div class="footer">
          <p>Bank Complaint AI Desk &bull; Regulatory Compliance Operations</p>
        </div>
      </div>
    </body>
    </html>
    """

    text_content = f"""
    Revisions Requested — Complaint #{complaint_id}
    
    Dear {agent_name or 'Agent'},
    
    Supervisor {supervisor_name} has reviewed your resolution draft for Complaint #{complaint_id} ({company}) and requested changes.
    
    Feedback / Instructions:
    --------------------------------------------------
    {reason}
    --------------------------------------------------
    
    Please sign into the Bank Complaint AI Desk, edit your response, and re-submit for approval.
    
    Bank Complaint AI Desk - Regulatory Compliance Operations
    """

    return dispatch_email_transport(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        client_origin=client_origin,
    )
