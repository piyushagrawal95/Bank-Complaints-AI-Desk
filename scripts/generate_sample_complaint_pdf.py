import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a'),
        alignment=0,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=14,
    )
    label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569'),
    )
    val_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0f172a'),
    )
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        'BodyDispute',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=15,
        textColor=colors.HexColor('#334155'),
        spaceAfter=10,
    )

    story = []

    # Header / Notice Banner
    story.append(Paragraph("CONSUMER FINANCIAL DISPUTE NOTICE", title_style))
    story.append(Paragraph("OFFICIAL NOTICE OF ERROR & BILLING INQUIRY (REGULATION E / CFPB)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=14))

    # Metadata Table
    meta_data = [
        [
            Paragraph("<b>Bank / Institution:</b>", label_style),
            Paragraph("JPMorgan Chase & Co.", val_style),
            Paragraph("<b>Date of Notice:</b>", label_style),
            Paragraph("October 28, 2026", val_style)
        ],
        [
            Paragraph("<b>Product Vertical:</b>", label_style),
            Paragraph("Checking or savings account", val_style),
            Paragraph("<b>Account Ending:</b>", label_style),
            Paragraph("•••• 8421", val_style)
        ],
        [
            Paragraph("<b>Dispute Issue:</b>", label_style),
            Paragraph("Problem with unauthorized transaction", val_style),
            Paragraph("<b>Disputed Amount:</b>", label_style),
            Paragraph("$840.00 USD", val_style)
        ],
        [
            Paragraph("<b>Consumer Email:</b>", label_style),
            Paragraph("rahul.sharma.dispute@example.com", val_style),
            Paragraph("<b>Customer Name:</b>", label_style),
            Paragraph("Rahul Sharma", val_style)
        ],
        [
            Paragraph("<b>State:</b>", label_style),
            Paragraph("NY", val_style),
            Paragraph("<b>ZIP Code:</b>", label_style),
            Paragraph("10001", val_style)
        ],
    ]

    t = Table(meta_data, colWidths=[110, 180, 95, 145])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # Detailed Grievance Section
    story.append(Paragraph("DETAILED GRIEVANCE & TRANSACTION SUMMARY", section_heading))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#e2e8f0'), spaceAfter=10))

    narrative_p1 = (
        "I am submitting this formal dispute notice regarding an unauthorized electronic funds withdrawal "
        "of $840.00 debited from my Premier Checking Account on October 24, 2026. The transaction appears on my "
        "statement as an external POS/wire transfer with memo 'EX-WIRE DISPATCH 7741' which I did not authorize, "
        "originate, or benefit from in any manner."
    )
    story.append(Paragraph(narrative_p1, body_style))

    narrative_p2 = (
        "Upon reviewing my mobile banking notifications on the morning of October 24, I immediately contacted Chase "
        "Fraud Customer Service within 2 hours of the debit. I filed an official Affidavit of Unauthorized Transaction "
        "(Reference Case #CH-992014) and requested that my debit card and electronic access credentials be locked. "
        "Under Electronic Fund Transfer Act (15 U.S.C. 1693) and CFPB Regulation E (12 CFR 1005.11), the financial "
        "institution is required to investigate the error and issue provisional credit within 10 business days if the "
        "investigation remains ongoing."
    )
    story.append(Paragraph(narrative_p2, body_style))

    narrative_p3 = (
        "Despite timely oral and written notification, Chase customer support representatives informed me on October 27 "
        "that my fraud claim was provisionally denied without reasonable investigation or review of the IP access logs. "
        "I have never shared my PIN, online passwords, or two-factor security codes. I am demanding an immediate re-examination "
        "of this claim, full reimbursement of the $840.00 unauthorized funds, and reversal of any resulting overdraft fees."
    )
    story.append(Paragraph(narrative_p3, body_style))

    # Declaration / Signoff
    story.append(Spacer(1, 10))
    story.append(Paragraph("CERTIFICATION & SIGNATURE", section_heading))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#e2e8f0'), spaceAfter=10))

    cert_text = (
        "I hereby certify under penalty of perjury that the statements above are true, accurate, and complete to the "
        "best of my knowledge. I request official written confirmation of your determination delivered to my email address "
        "at <b>rahul.sharma.dispute@example.com</b>."
    )
    story.append(Paragraph(cert_text, body_style))
    story.append(Spacer(1, 8))

    sign_data = [
        [Paragraph("<b>Complainant Signature:</b> Rahul Sharma (Electronically Verified)", val_style),
         Paragraph("<b>Submission Channel:</b> Online Dispute Upload", val_style)]
    ]
    sign_table = Table(sign_data, colWidths=[280, 250])
    sign_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sign_table)

    doc.build(story)
    print(f"Generated PDF at: {output_path}")

if __name__ == '__main__':
    desktop_path = os.path.expanduser(r"~\Desktop\sample_bank_complaint.pdf")
    generate_pdf(desktop_path)
    # Also save a copy in the workspace folder
    local_path = os.path.join(os.path.dirname(__file__), "sample_bank_complaint.pdf")
    generate_pdf(local_path)
