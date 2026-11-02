from datetime import datetime
import html
import json
import logging
import os
import re
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
            sender_name = (os.getenv("BREVO_SENDER_NAME") or getattr(settings, "brevo_sender_name", "") or "Bank Complaint AI Desk").strip()
            if not sender_email:
                raise ValueError("BREVO_SENDER_EMAIL is not configured in .env")
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

    # Direct secure transports: Brevo REST API -> Resend API -> SMTP
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
    """Sends official resolution approval notification to the consumer in a unified bank letterhead format."""
    inst_name = (company or "Financial Institution").strip()
    prod_name = (product or "Banking Service").strip()
    issue_name = (issue or "Consumer Grievance").strip()
    current_date_str = datetime.now().strftime("%B %d, %Y")
    subject = f"Official Dispute Resolution Notice — {inst_name} [Ref: #{complaint_id}]"

    clean_text = (resolution_text or "").strip()
    # Check if the letter already begins with a formal greeting
    has_greeting = bool(re.match(r"(?i)^(dear|hello|to\s+whom|attention|greetings)", clean_text))

    # Convert paragraphs into clean HTML paragraphs
    raw_paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    if not has_greeting and raw_paragraphs:
        raw_paragraphs.insert(0, "Dear Customer,")

    body_paragraphs_html = "".join(
        f'<p style="margin: 0 0 16px 0; color: #1e293b; font-size: 15px; line-height: 1.7; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif;">'
        f'{html.escape(p).replace(chr(10), "<br>")}'
        f'</p>'
        for p in raw_paragraphs
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(subject)}</title>
</head>
<body style="margin: 0; padding: 24px 12px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #0f172a;">
  <div style="max-width: 640px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-top: 5px solid #1e40af; border-radius: 12px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05); overflow: hidden;">
    
    <!-- Letterhead Header -->
    <div style="padding: 28px 32px 20px; border-bottom: 1px solid #f1f5f9;">
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="vertical-align: top;">
            <div style="font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">{html.escape(inst_name)}</div>
            <div style="font-size: 13px; color: #64748b; margin-top: 3px; font-weight: 500;">Consumer Dispute Resolution &amp; Regulatory Compliance Desk</div>
          </td>
          <td style="text-align: right; vertical-align: top;">
            <span style="display: inline-block; background-color: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 10px; border-radius: 9999px;">
              Formally Resolved
            </span>
          </td>
        </tr>
      </table>

      <!-- Dispute Reference Metadata Ribbon -->
      <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-top: 18px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr>
            <td style="padding: 3px 0; color: #64748b; width: 35%;">Case Reference ID:</td>
            <td style="padding: 3px 0; color: #0f172a; font-weight: 700;">#{complaint_id}</td>
          </tr>
          <tr>
            <td style="padding: 3px 0; color: #64748b;">Product / Instrument:</td>
            <td style="padding: 3px 0; color: #0f172a; font-weight: 600;">{html.escape(prod_name)}</td>
          </tr>
          <tr>
            <td style="padding: 3px 0; color: #64748b;">Dispute Subject:</td>
            <td style="padding: 3px 0; color: #0f172a;">{html.escape(issue_name)}</td>
          </tr>
          <tr>
            <td style="padding: 3px 0; color: #64748b;">Date of Determination:</td>
            <td style="padding: 3px 0; color: #0f172a;">{current_date_str}</td>
          </tr>
        </table>
      </div>
    </div>

    <!-- Letter Body (Unified Narrative) -->
    <div style="padding: 28px 32px 16px;">
      {body_paragraphs_html}
    </div>

    <!-- Compliance Determination & Audit Trail Footer -->
    <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; font-size: 12px; color: #64748b; line-height: 1.6;">
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 12px;">
        <tr>
          <td style="color: #475569; font-weight: 600;">Compliance Approval Record:</td>
          <td style="text-align: right; color: #0f172a; font-weight: 600;">{html.escape(approver_name)} ({html.escape(approver_role.title())})</td>
        </tr>
      </table>
      <div style="border-top: 1px dashed #cbd5e1; padding-top: 10px;">
        This dispute determination was conducted in strict adherence with federal consumer financial protection statutes, including <strong>Regulation E (12 CFR Part 1005)</strong>, <strong>Regulation Z (12 CFR Part 1026)</strong>, and CFPB statutory timelines. Please retain Case Reference <strong>#{complaint_id}</strong> for your records.
      </div>
    </div>

    <!-- Bottom Email Disclaimer -->
    <div style="background-color: #0f172a; padding: 16px 32px; text-align: center; font-size: 11px; color: #94a3b8; line-height: 1.5;">
      Bank Complaint AI Desk &bull; Consumer Dispute Compliance Department<br>
      Official Electronic Notification &bull; Do not reply directly to this automated dispatch.
    </div>

  </div>
</body>
</html>"""

    # Plain text version for non-HTML email clients
    text_content = f"""{inst_name.upper()}
CONSUMER DISPUTE RESOLUTION & COMPLIANCE DESK
================================================================================
Case Reference ID: #{complaint_id}
Product: {prod_name}
Dispute Subject: {issue_name}
Date of Determination: {current_date_str}
Status: Formally Resolved & Approved
================================================================================

{clean_text}

================================================================================
COMPLIANCE DETERMINATION & AUDIT RECORD:
Approved By: {approver_name} ({approver_role.title()})
Governing Statutes: Regulation E (12 CFR Part 1005) / Regulation Z (12 CFR Part 1026)
Reference Identifier: #{complaint_id}

This determination adheres to federal banking compliance standards under CFPB rules.
Please retain Case Reference #{complaint_id} for your records.
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

    safe_sup = html.escape(supervisor_name or 'Supervisor')
    safe_agent = html.escape(agent_name or 'Agent')
    safe_company = html.escape(company or 'Bank')
    safe_product = html.escape(product or 'Service')
    safe_issue = html.escape(issue or 'Customer Dispute')
    safe_draft = html.escape(response_draft[:800])
    portal_link = (settings.frontend_origin or "https://bank-complaints-ai-desk.vercel.app").rstrip('/')

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
        <p>Dear {safe_sup},</p>
        <p>Agent <strong>{safe_agent}</strong> has submitted an official resolution draft for Complaint <strong>#{complaint_id}</strong>. Please log into the Bank Complaint AI Desk to review, customize if necessary, and formally approve the response.</p>
        
        <div class="meta-box">
          <div class="meta-row">
            <span class="meta-label">Complaint ID:</span>
            <span class="meta-value">#{complaint_id}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Bank / Institution:</span>
            <span class="meta-value">{safe_company}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Product:</span>
            <span class="meta-value">{safe_product}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Dispute Issue:</span>
            <span class="meta-value">{safe_issue}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">Submitted By:</span>
            <span class="meta-value">{safe_agent}</span>
          </div>
        </div>

        <p style="font-weight: 600; font-size: 14px; margin-bottom: 6px;">Draft Resolution Letter Preview:</p>
        <div class="draft-preview">{safe_draft}...</div>

        <p style="font-size: 14px; color: #475569;">Prompt approval ensures timely delivery to the consumer within mandatory regulatory windows (e.g. Regulation E / Z).</p>

        <div style="text-align: center; margin: 26px 0 20px;">
          <a href="{portal_link}" style="display: inline-block; background-color: #1e40af; color: #ffffff; font-weight: 700; font-size: 14px; text-decoration: none; padding: 12px 28px; border-radius: 8px; box-shadow: 0 4px 12px rgba(30, 64, 175, 0.25);">
            👉 Log in to Approvals Portal
          </a>
        </div>

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
        <p>Dear {html.escape(agent_name or 'Agent')},</p>
        <p>Supervisor <strong>{html.escape(supervisor_name or 'Supervisor')}</strong> has reviewed your resolution draft for Complaint <strong>#{complaint_id}</strong> ({html.escape(company or 'Bank')}) and requested modifications before it can be approved for customer dispatch.</p>
        
        <p style="font-weight: 600; font-size: 14px; margin-bottom: 6px;">Supervisor Feedback & Instructions:</p>
        <div class="feedback-box">{html.escape(reason or '')}</div>

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
