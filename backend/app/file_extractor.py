import csv
import io
import logging
import re
from datetime import date

logger = logging.getLogger(__name__)

STANDARD_PRODUCTS = [
    "Checking or savings account",
    "Credit card or prepaid card",
    "Credit reporting, credit repair services, or other personal consumer reports",
    "Debt collection",
    "Money transfer, virtual currency, or money service",
    "Mortgage",
    "Payday loan, title loan, or personal loan",
    "Student loan",
    "Vehicle loan or lease",
]

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR"
}

BANK_KEYWORDS = [
    (["jpmorgan", "chase"], "JPMorgan Chase & Co."),
    (["bank of america", "bofa"], "Bank of America, N.A."),
    (["wells fargo"], "Wells Fargo & Company"),
    (["citibank", "citi "], "Citibank, N.A."),
    (["capital one"], "Capital One Financial Corporation"),
    (["pnc"], "PNC Bank, N.A."),
    (["discover"], "Discover Bank"),
    (["truist"], "Truist Financial Corporation"),
    (["us bank", "u.s. bank", "us bancorp"], "U.S. Bancorp"),
    (["goldman sachs"], "Goldman Sachs Bank USA"),
    (["td bank"], "TD Bank US Holding Company"),
    (["synchrony"], "Synchrony Financial"),
    (["american express", "amex"], "American Express Company"),
    (["barclays"], "Barclays Bank Delaware"),
    (["navient"], "Navient Solutions, LLC"),
]


def extract_raw_text(filename: str, content: bytes) -> str:
    """Extracts raw textual content from PDF, DOCX, XLSX, XLS, CSV, or TXT."""
    fn = filename.lower()

    if fn.endswith(".pdf"):
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = []
        for p in reader.pages:
            t = p.extract_text()
            if t:
                pages.append(t)
        return "\n\n".join(pages).strip()

    if fn.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        return "\n\n".join(paragraphs).strip()

    if fn.endswith(".xlsx") or fn.endswith(".xls") or fn.endswith(".csv"):
        import pandas as pd
        try:
            if fn.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content), dtype=str)
            else:
                df = pd.read_excel(io.BytesIO(content), dtype=str)
            lines = ["Columns: " + ", ".join(str(c) for c in df.columns if not str(c).startswith("Unnamed"))]
            for _, row in df.head(100).iterrows():
                row_items = [f"{col}: {val}" for col, val in row.items() if pd.notna(val) and str(val).strip()]
                if row_items:
                    lines.append(" | ".join(row_items))
            return "\n".join(lines).strip()
        except Exception:
            return content.decode("utf-8", errors="replace").strip()

    return content.decode("utf-8", errors="replace").strip()


def parse_complaint_from_text(raw_text: str, filename: str = "") -> dict:
    """Parses complaint attributes, consumer email, and narrative from text chunk."""
    lower_text = raw_text.lower()

    # 1. Consumer Email extraction
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", raw_text)
    consumer_email = email_match.group(0).strip().lower() if email_match else ""

    # 2. Company / Bank identification (explicit key-value with newline tolerance)
    company = ""
    comp_match = re.search(
        r"(?:bank\s*/\s*institution|company|bank|financial institution)\s*:\s*[\r\n]*\s*([^\r\n]+)",
        raw_text,
        re.IGNORECASE,
    )
    if comp_match:
        c_cand = comp_match.group(1).strip()
        if len(c_cand) > 3 and not c_cand.lower().startswith("dispute") and not c_cand.lower().startswith("product"):
            for keys, bname in BANK_KEYWORDS:
                if any(k in c_cand.lower() for k in keys):
                    company = bname
                    break
            if not company:
                company = c_cand

    if not company:
        for keys, bname in BANK_KEYWORDS:
            if any(k in lower_text for k in keys):
                company = bname
                break
    if not company:
        company = "JPMorgan Chase & Co."

    # 3. Product inference
    product = ""
    prod_match = re.search(
        r"(?:product\s*vertical|account\s*product|product)\s*:\s*[\r\n]*\s*([^\r\n]+)",
        raw_text,
        re.IGNORECASE,
    )
    if prod_match:
        p_cand = prod_match.group(1).strip()
        for sp in STANDARD_PRODUCTS:
            if sp.lower() in p_cand.lower() or p_cand.lower() in sp.lower():
                product = sp
                break
        if not product and len(p_cand) > 4:
            product = p_cand

    if not product:
        if "credit card" in lower_text or "prepaid card" in lower_text:
            product = "Credit card or prepaid card"
        elif "mortgage" in lower_text:
            product = "Mortgage"
        elif "debt" in lower_text and ("collect" in lower_text or "agency" in lower_text):
            product = "Debt collection"
        elif "credit report" in lower_text or "bureau" in lower_text:
            product = "Credit reporting, credit repair services, or other personal consumer reports"
        elif "vehicle" in lower_text or "auto loan" in lower_text or "car loan" in lower_text:
            product = "Vehicle loan or lease"
        elif "wire" in lower_text or "money transfer" in lower_text or "remittance" in lower_text:
            product = "Money transfer, virtual currency, or money service"
        elif "student loan" in lower_text:
            product = "Student loan"
        elif "payday" in lower_text or "personal loan" in lower_text:
            product = "Payday loan, title loan, or personal loan"
        else:
            product = "Checking or savings account"

    # 4. Issue extraction
    issue = ""
    issue_match = re.search(
        r"(?:dispute\s*issue|primary\s*issue|dispute\s*reason|issue|subject)\s*:\s*[\r\n]*\s*([^\r\n]+)",
        raw_text,
        re.IGNORECASE,
    )
    if issue_match:
        i_cand = issue_match.group(1).strip()
        if len(i_cand) > 4 and not i_cand.lower().startswith("bank") and not i_cand.lower().startswith("product"):
            issue = i_cand[:120]

    if not issue:
        if "unauthorized" in lower_text:
            issue = "Problem with unauthorized transaction"
        elif "duplicate" in lower_text or "double" in lower_text:
            issue = "Billing error or duplicate charge"
        elif "late fee" in lower_text:
            issue = "Excessive or incorrect fee assessment"
        elif "wire" in lower_text:
            issue = "Problem with wire transfer or delayed funds"
        else:
            issue = "Customer dispute regarding account or transaction"

    # 5. State & ZIP identification
    state = "NY"
    zip_code = ""

    state_match = re.search(r"(?:state)\s*:\s*[\r\n]*\s*([A-Za-z]{2})", raw_text, re.IGNORECASE)
    if state_match:
        cand_state = state_match.group(1).strip().upper()
        if cand_state in US_STATES:
            state = cand_state

    zip_match = re.search(r"(?:zip|postal)(?:\s*code)?\s*:\s*[\r\n]*\s*(\d{5})", raw_text, re.IGNORECASE)
    if zip_match:
        zip_code = zip_match.group(1).strip()
    elif not zip_code:
        zm = re.search(r"\b(\d{5})(?:-\d{4})?\b", raw_text)
        if zm:
            zip_code = zm.group(1)

    # 6. Narrative cleaning (extract grievance text, filter out metadata label lines)
    clean_lines = []
    for line in raw_text.splitlines():
        l_strip = line.strip()
        if not l_strip:
            continue
        if re.match(
            r"(?i)^(?:bank\s*/\s*institution|product\s*vertical|consumer\s*email|dispute\s*issue|customer\s*name|date\s*of\s*notice|state|zip\s*code|---)\s*:",
            l_strip,
        ):
            continue
        if l_strip.lower() in [company.lower(), product.lower(), consumer_email.lower(), issue.lower()]:
            continue
        clean_lines.append(l_strip)

    narrative = "\n".join(clean_lines).strip()
    if len(narrative) < 15:
        narrative = raw_text.strip()
    if len(narrative) > 8000:
        narrative = narrative[:8000] + "... [narrative truncated]"

    return {
        "filename": filename,
        "product": product,
        "sub_product": None,
        "issue": issue,
        "sub_issue": None,
        "company": company,
        "state": state,
        "zip_code": zip_code,
        "consumer_email": consumer_email,
        "narrative": narrative,
        "date_received": date.today().isoformat(),
        "submitted_via": "File Upload" if filename else "Web Portal",
    }


def extract_complaints_from_file(filename: str, content: bytes) -> dict:
    """Extracts either a single complaint or multiple complaints from PDF, Word, Excel, CSV."""
    fn = filename.lower()

    # 1. Process Excel / CSV files
    if fn.endswith(".xlsx") or fn.endswith(".xls") or fn.endswith(".csv"):
        import pandas as pd
        try:
            if fn.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content), dtype=str)
            else:
                df = pd.read_excel(io.BytesIO(content), dtype=str)

            if len(df) > 1:
                def find_col(aliases):
                    for col in df.columns:
                        c_clean = str(col).lower().replace("_", " ").replace("-", " ").strip()
                        for a in aliases:
                            if a in c_clean:
                                return col
                    return None

                c_company = find_col(["company", "bank", "institution", "lender", "entity"])
                c_product = find_col(["product", "category", "vertical", "account type"])
                c_issue = find_col(["issue", "subject", "dispute", "reason", "type"])
                c_email = find_col(["email", "mail", "consumer email", "customer email"])
                c_narrative = find_col(["narrative", "story", "complaint", "details", "description", "comment", "text"])
                c_state = find_col(["state"])
                c_zip = find_col(["zip", "postal"])
                c_date = find_col(["date", "received", "timestamp"])

                records = []
                for _, row in df.iterrows():
                    narr = ""
                    if c_narrative and pd.notna(row.get(c_narrative)):
                        narr = str(row[c_narrative]).strip()
                    if not narr:
                        items = [f"{col}: {val}" for col, val in row.items() if pd.notna(val) and str(val).strip()]
                        narr = " | ".join(items)

                    if len(narr) < 10:
                        continue

                    company_val = str(row[c_company]).strip() if c_company and pd.notna(row.get(c_company)) else "JPMorgan Chase & Co."
                    product_val = str(row[c_product]).strip() if c_product and pd.notna(row.get(c_product)) else "Checking or savings account"
                    issue_val = str(row[c_issue]).strip() if c_issue and pd.notna(row.get(c_issue)) else "Dispute reported"
                    email_val = str(row[c_email]).strip().lower() if c_email and pd.notna(row.get(c_email)) else ""
                    state_val = str(row[c_state]).strip().upper()[:2] if c_state and pd.notna(row.get(c_state)) else "NY"
                    zip_val = str(row[c_zip]).strip()[:10] if c_zip and pd.notna(row.get(c_zip)) else ""
                    date_val = str(row[c_date]).strip()[:10] if c_date and pd.notna(row.get(c_date)) else date.today().isoformat()

                    records.append({
                        "filename": f"{filename} (Row #{len(records)+1})",
                        "company": company_val,
                        "product": product_val,
                        "sub_product": None,
                        "issue": issue_val,
                        "sub_issue": None,
                        "consumer_email": email_val,
                        "state": state_val if state_val in US_STATES else "NY",
                        "zip_code": zip_val,
                        "narrative": narr,
                        "date_received": date_val,
                        "submitted_via": "Bulk File Upload",
                    })

                if len(records) > 1:
                    return {
                        "is_batch": True,
                        "count": len(records),
                        "records": records,
                        "extracted": records[0],
                        "raw_text": f"Found {len(records)} dispute records in spreadsheet.",
                    }
        except Exception as e:
            logger.warning("Error parsing multi-row spreadsheet: %s", e)

    # 2. Check PDF / Text for multiple distinct sections
    raw_text = extract_raw_text(filename, content)

    split_pattern = r"(?i)(?:^|\n)(?:[-=]{3,}\s*(?:dispute|complaint|record|case)\s*#?\d*.*?[-=]{3,})"
    chunks = re.split(split_pattern, raw_text)

    records = []
    for idx, chunk in enumerate(chunks):
        chunk_clean = chunk.strip()
        has_email = "@" in chunk_clean
        has_bank = any(k in chunk_clean.lower() for keys, b in BANK_KEYWORDS for k in keys)
        has_dispute = any(w in chunk_clean.lower() for w in ["unauthorized", "charge", "fee", "dispute", "statement", "refund", "delayed"])

        if not (has_email or (has_bank and has_dispute)) or len(chunk_clean) < 40:
            continue

        p = parse_complaint_from_text(chunk_clean, f"{filename} (Record #{len(records)+1})")
        if p and len(p.get("narrative", "")) > 10:
            records.append(p)

    if len(records) > 1:
        return {
            "is_batch": True,
            "count": len(records),
            "records": records,
            "extracted": records[0],
            "raw_text": raw_text,
        }

    # 3. Default single complaint
    single = parse_complaint_from_text(raw_text, filename)
    return {
        "is_batch": False,
        "count": 1,
        "records": [single],
        "extracted": single,
        "raw_text": raw_text,
    }
