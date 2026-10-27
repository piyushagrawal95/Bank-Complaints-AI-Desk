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

STATE_NAMES = {
    "CALIFORNIA": "CA", "NEW YORK": "NY", "TEXAS": "TX", "FLORIDA": "FL",
    "ILLINOIS": "IL", "PENNSYLVANIA": "PA", "OHIO": "OH", "GEORGIA": "GA",
    "MICHIGAN": "MI", "NORTH CAROLINA": "NC", "NEW JERSEY": "NJ", "VIRGINIA": "VA",
    "WASHINGTON": "WA", "MASSACHUSETTS": "MA", "ARIZONA": "AZ", "COLORADO": "CO",
}

COMMON_BANKS = [
    "JPMorgan Chase & Co.",
    "Bank of America, N.A.",
    "Wells Fargo & Company",
    "Citibank, N.A.",
    "Capital One Financial Corporation",
    "U.S. Bancorp",
    "PNC Bank, N.A.",
    "Truist Financial Corporation",
    "Goldman Sachs Bank USA",
    "Discover Bank",
    "TD Bank US Holding Company",
    "Synchrony Financial",
    "American Express Company",
    "Barclays Bank Delaware",
    "Navient Solutions, LLC",
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

    if fn.endswith(".xlsx") or fn.endswith(".xls"):
        import pandas as pd
        # Read first available sheet
        df = pd.read_excel(io.BytesIO(content), dtype=str)
        # Convert non-empty cells to readable text representation
        lines = []
        # Check column headers
        lines.append("Columns: " + ", ".join(str(c) for c in df.columns if not str(c).startswith("Unnamed")))
        for _, row in df.head(100).iterrows():
            row_items = [f"{col}: {val}" for col, val in row.items() if pd.notna(val) and str(val).strip()]
            if row_items:
                lines.append(" | ".join(row_items))
        return "\n".join(lines).strip()

    if fn.endswith(".csv"):
        import pandas as pd
        try:
            df = pd.read_csv(io.BytesIO(content), dtype=str)
            lines = ["Columns: " + ", ".join(str(c) for c in df.columns if not str(c).startswith("Unnamed"))]
            for _, row in df.head(100).iterrows():
                row_items = [f"{col}: {val}" for col, val in row.items() if pd.notna(val) and str(val).strip()]
                if row_items:
                    lines.append(" | ".join(row_items))
            return "\n".join(lines).strip()
        except Exception:
            text = content.decode("utf-8", errors="replace")
            return text

    # Default text decode for txt or unknown
    return content.decode("utf-8", errors="replace").strip()


def parse_complaint_from_text(raw_text: str, filename: str = "") -> dict:
    """Parses complaint attributes, consumer email, and narrative from raw text."""
    lower_text = raw_text.lower()

    # 1. Consumer Email extraction
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", raw_text)
    consumer_email = email_match.group(0).strip() if email_match else ""

    # 2. Product inference
    product = "Checking or savings account"
    if "credit card" in lower_text or "prepaid card" in lower_text:
        product = "Credit card or prepaid card"
    elif "mortgage" in lower_text:
        product = "Mortgage"
    elif "debt" in lower_text and ("collect" in lower_text or "agency" in lower_text):
        product = "Debt collection"
    elif "credit report" in lower_text or "credit reporting" in lower_text or "bureau" in lower_text:
        product = "Credit reporting, credit repair services, or other personal consumer reports"
    elif "student loan" in lower_text:
        product = "Student loan"
    elif "vehicle" in lower_text or "car loan" in lower_text or "auto loan" in lower_text:
        product = "Vehicle loan or lease"
    elif "money transfer" in lower_text or "wire" in lower_text or "remittance" in lower_text:
        product = "Money transfer, virtual currency, or money service"
    elif "payday" in lower_text or "personal loan" in lower_text:
        product = "Payday loan, title loan, or personal loan"

    # 3. Company / Bank identification
    company = "JPMorgan Chase & Co."
    for b in COMMON_BANKS:
        # Check standard short name tokens
        tokens = [t.lower() for t in b.replace(",", "").replace(".", "").split() if len(t) > 3]
        if any(token in lower_text for token in tokens):
            company = b
            break

    # Look for explicit field: Company: XYZ or Bank: XYZ
    comp_match = re.search(r"(?:company|bank|financial institution)\s*:\s*([^\n\r,]+)", raw_text, re.IGNORECASE)
    if comp_match:
        c_val = comp_match.group(1).strip()
        if len(c_val) >= 3:
            company = c_val

    # 4. State & ZIP identification
    state = "NY"
    zip_code = ""

    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", raw_text)
    if zip_match:
        zip_code = zip_match.group(1)

    state_match = re.search(r"(?:state)\s*:\s*([A-Za-z]{2,20})", raw_text, re.IGNORECASE)
    if state_match:
        cand_state = state_match.group(1).strip().upper()
        if cand_state in US_STATES:
            state = cand_state
        elif cand_state in STATE_NAMES:
            state = STATE_NAMES[cand_state]
    else:
        # Check isolated 2-letter tokens in uppercase
        for st in US_STATES:
            if re.search(r"\b" + st + r"\b", raw_text):
                state = st
                break

    # 5. Issue extraction
    issue = ""
    issue_match = re.search(r"(?:issue|subject|regarding|re)\s*:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
    if issue_match:
        cand_issue = issue_match.group(1).strip()
        if len(cand_issue) > 4:
            issue = cand_issue[:100]

    if not issue:
        # Infer issue based on product or first meaningful line
        lines = [l.strip() for l in raw_text.splitlines() if len(l.strip()) > 15]
        if lines:
            issue = lines[0][:100]
        else:
            issue = "Managing an account or service issue"

    # 6. Narrative
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

    # 1. Check Excel / CSV for multiple rows
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

                c_company = find_col(["company", "bank", "institution", "lender"])
                c_product = find_col(["product", "category", "vertical", "account type"])
                c_issue = find_col(["issue", "subject", "dispute", "reason", "type"])
                c_email = find_col(["email", "mail", "consumer email", "customer email"])
                c_narrative = find_col(["narrative", "story", "complaint", "details", "description", "comment"])
                c_state = find_col(["state"])
                c_zip = find_col(["zip", "postal"])
                c_date = find_col(["date", "received"])

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

                    parsed = parse_complaint_from_text(narr, filename)

                    if c_company and pd.notna(row.get(c_company)) and str(row[c_company]).strip():
                        parsed["company"] = str(row[c_company]).strip()
                    if c_product and pd.notna(row.get(c_product)) and str(row[c_product]).strip():
                        parsed["product"] = str(row[c_product]).strip()
                    if c_issue and pd.notna(row.get(c_issue)) and str(row[c_issue]).strip():
                        parsed["issue"] = str(row[c_issue]).strip()
                    if c_email and pd.notna(row.get(c_email)) and str(row[c_email]).strip():
                        parsed["consumer_email"] = str(row[c_email]).strip().lower()
                    if c_state and pd.notna(row.get(c_state)) and str(row[c_state]).strip():
                        parsed["state"] = str(row[c_state]).strip().upper()[:2]
                    if c_zip and pd.notna(row.get(c_zip)) and str(row[c_zip]).strip():
                        parsed["zip_code"] = str(row[c_zip]).strip()[:10]
                    if c_date and pd.notna(row.get(c_date)) and str(row[c_date]).strip():
                        parsed["date_received"] = str(row[c_date]).strip()[:10]

                    records.append(parsed)

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

    split_pattern = r"(?i)(?:^|\n)(?:[-=]{3,}\s*(?:dispute|complaint|record|case)\s*#?\d*.*?[-=]{3,}|(?:dispute|complaint|case)\s*#\s*\d+\s*:)"
    chunks = re.split(split_pattern, raw_text)
    meaningful_chunks = [c.strip() for c in chunks if len(c.strip()) > 50]

    if len(meaningful_chunks) > 1:
        records = []
        for idx, chunk in enumerate(meaningful_chunks, 1):
            p = parse_complaint_from_text(chunk, f"{filename} (Record #{idx})")
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
