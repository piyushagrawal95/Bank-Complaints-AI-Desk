import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings
from app.db import pool
from app.deps import get_current_user
from app.email_service import send_complaint_approval_email, send_supervisor_approval_request_email
from app.file_extractor import extract_raw_text, parse_complaint_from_text, extract_complaints_from_file
from app.llm.analysis import (
    BASIS_METADATA,
    BASIS_NARRATIVE,
    analyze_metadata,
    analyze_narrative,
    draft_reply,
)
from app.llm.client import LLMError
from app.llm.embedding import embed_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/complaints", tags=["complaints"], dependencies=[Depends(get_current_user)])

LIST_COLUMNS = (
    "complaint_id, date_received, product, sub_product, issue, company, "
    "state, submitted_via, company_response_to_consumer, timely_response, consumer_email"
)


class DraftReplyIn(BaseModel):
    custom_instructions: str | None = Field(default=None, max_length=500)


class UpdateEmailIn(BaseModel):
    consumer_email: EmailStr


class CreateComplaintIn(BaseModel):
    product: str = Field(min_length=2, max_length=200)
    sub_product: str | None = Field(default=None, max_length=200)
    issue: str = Field(min_length=2, max_length=200)
    sub_issue: str | None = Field(default=None, max_length=200)
    company: str = Field(min_length=2, max_length=200)
    state: str | None = Field(default=None, max_length=10)
    zip_code: str | None = Field(default=None, max_length=20)
    consumer_email: str | None = Field(default=None, max_length=255)
    narrative: str = Field(min_length=5, max_length=15000)
    date_received: date | None = None
    submitted_via: str = Field(default="Web Portal", max_length=50)


class RequestApprovalIn(BaseModel):
    response_text: str = Field(min_length=10)


class ApproveResponseIn(BaseModel):
    response_text: str = Field(min_length=10)


@router.get("")
def list_complaints(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    product: str | None = None,
    company: str | None = None,
    state: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
):
    conditions = []
    params = []

    if product:
        conditions.append("product = %s")
        params.append(product)
    if company:
        conditions.append("company ILIKE %s")
        params.append(f"%{company}%")
    if state:
        conditions.append("state = %s")
        params.append(state.upper())
    if date_from:
        conditions.append("date_received >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("date_received <= %s")
        params.append(date_to)
    if q:
        conditions.append(
            "(issue ILIKE %s OR sub_issue ILIKE %s OR company ILIKE %s OR consumer_email ILIKE %s)"
        )
        params.extend([f"%{q}%"] * 4)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * page_size

    try:
        with pool.connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM complaints {where}", params
            ).fetchone()["n"]
            rows = conn.execute(
                f"SELECT {LIST_COLUMNS} FROM complaints {where} "
                "ORDER BY date_received DESC, complaint_id DESC LIMIT %s OFFSET %s",
                [*params, page_size, offset],
            ).fetchall()
    except Exception:
        logger.exception("Database error while listing complaints")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "items": rows,
    }


@router.get("/meta/products")
def list_products():
    try:
        with pool.connection() as conn:
            rows = conn.execute(
                "SELECT product, COUNT(*) AS count FROM complaints "
                "GROUP BY product ORDER BY count DESC"
            ).fetchall()
    except Exception:
        logger.exception("Database error while listing products")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")
    return rows


@router.post("/extract-file")
async def extract_complaint_file(file: UploadFile = File(...)):
    """Extracts text, consumer email, and metadata fields from uploaded PDF, Word, Excel, or CSV."""
    allowed_exts = (".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt")
    filename = file.filename or "uploaded_file"
    if not any(filename.lower().endswith(ext) for ext in allowed_exts):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Please upload a PDF, Word (.docx), Excel (.xlsx/.xls), CSV, or text file.",
        )

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds maximum 15MB limit.")

        res = extract_complaints_from_file(filename, content)
        return {
            "success": True,
            "filename": filename,
            "is_batch": res["is_batch"],
            "count": res["count"],
            "records": res["records"],
            "extracted": res["extracted"],
            "character_count": len(res.get("raw_text", "")),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error extracting complaint document")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(exc)}")


@router.post("/create")
def create_complaint(body: CreateComplaintIn, user: dict = Depends(get_current_user)):
    """Creates a new complaint in the database, making it immediately searchable and accessible."""
    date_rcvd = body.date_received or date.today()
    clean_email = (body.consumer_email or "").strip().lower() or None
    clean_state = (body.state or "").strip().upper() or None
    clean_zip = (body.zip_code or "").strip() or None

    try:
        with pool.connection() as conn:
            # Generate next unique complaint_id
            max_row = conn.execute("SELECT COALESCE(MAX(complaint_id), 10000000) AS max_id FROM complaints").fetchone()
            new_id = int(max_row["max_id"]) + 1

            insert_sql = """
                INSERT INTO complaints (
                    complaint_id, date_received, product, sub_product, issue, sub_issue,
                    narrative, company, state, zip_code, submitted_via,
                    consumer_email, timely_response, date_sent_to_company
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s
                )
                RETURNING *;
            """
            row = conn.execute(
                insert_sql,
                [
                    new_id,
                    date_rcvd,
                    body.product.strip(),
                    body.sub_product.strip() if body.sub_product else None,
                    body.issue.strip(),
                    body.sub_issue.strip() if body.sub_issue else None,
                    body.narrative.strip(),
                    body.company.strip(),
                    clean_state,
                    clean_zip,
                    body.submitted_via,
                    clean_email,
                    date_rcvd,
                ],
            ).fetchone()

            # Optional: attempt generating an embedding in background so vector similarity works immediately
            try:
                if body.narrative and len(body.narrative.strip()) >= 10:
                    text_for_embed = f"{body.product} - {body.issue}: {body.narrative[:1000]}"
                    emb = embed_query(text_for_embed)
                    vec_str = f"[{','.join(str(v) for v in emb)}]"
                    conn.execute(
                        "INSERT INTO complaint_embeddings (complaint_id, embedding) "
                        "VALUES (%s, %s::vector) ON CONFLICT (complaint_id) DO NOTHING",
                        [new_id, vec_str],
                    )
            except Exception as emb_exc:
                logger.warning(f"Embedding generation deferred for new complaint {new_id}: {emb_exc}")

            return {
                "success": True,
                "message": f"Complaint #{new_id} recorded successfully.",
                "complaint": row,
            }
    except Exception as exc:
        logger.exception("Database error creating complaint")
        raise HTTPException(status_code=503, detail="Failed to record complaint in database.")


@router.get("/pending-approvals")
def list_pending_approvals(user=Depends(get_current_user)):
    """Lists all complaints with draft responses currently awaiting supervisor approval."""
    sql = """
        SELECT 
            c.complaint_id, c.date_received, c.product, c.issue, c.company,
            c.state, c.consumer_email, c.narrative,
            cr.response_text, cr.requested_by_name, cr.requested_by_role,
            cr.requested_at, cr.status, cr.assigned_to_name, cr.assigned_to_email
        FROM complaints c
        JOIN complaint_responses cr ON c.complaint_id = cr.complaint_id
        WHERE cr.status = 'pending_approval'
        ORDER BY cr.requested_at DESC NULLS LAST;
    """
    try:
        with pool.connection() as conn:
            rows = conn.execute(sql).fetchall()
        return {"count": len(rows), "items": rows}
    except Exception as exc:
        logger.exception("Error fetching pending approvals")
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending approvals: {str(exc)}")


@router.get("/{complaint_id}")
def get_complaint(complaint_id: int):
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT * FROM complaints WHERE complaint_id = %s", [complaint_id]
            ).fetchone()
            analysis = conn.execute(
                "SELECT category, summary, model, basis FROM complaint_analysis "
                "WHERE complaint_id = %s",
                [complaint_id],
            ).fetchone()
            response = conn.execute(
                "SELECT response_text, requested_by_name, requested_by_role, requested_at, "
                "approved_by_name, approved_by_role, status, approved_at, dispatched_at "
                "FROM complaint_responses WHERE complaint_id = %s",
                [complaint_id],
            ).fetchone()
    except Exception:
        logger.exception("Database error while reading complaint")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {**row, "analysis": analysis, "response": response}





class BatchCreateIn(BaseModel):
    complaints: list[CreateComplaintIn]


@router.post("/batch-create")
def batch_create_complaints(body: BatchCreateIn, user: dict = Depends(get_current_user)):
    """Inserts multiple complaints into the database in a single batch operation."""
    if not body.complaints:
        raise HTTPException(status_code=400, detail="No complaints provided for batch creation.")
    if len(body.complaints) > 200:
        raise HTTPException(status_code=400, detail="Batch exceeds maximum limit of 200 complaints per upload.")

    created_list = []
    try:
        with pool.connection() as conn:
            # Find current max complaint_id
            max_row = conn.execute(
                "SELECT COALESCE(MAX(complaint_id), 1700000) AS max_id FROM complaints"
            ).fetchone()
            current_id = int(max_row["max_id"]) if max_row else 1700000

            insert_sql = """
                INSERT INTO complaints (
                    complaint_id, date_received, product, sub_product, issue, sub_issue,
                    narrative, company, state, zip_code, submitted_via,
                    consumer_email, timely_response, date_sent_to_company
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s
                )
                RETURNING complaint_id, product, company, issue, consumer_email, date_received;
            """

            for item in body.complaints:
                current_id += 1
                date_rcvd = item.date_received or date.today()
                clean_email = (item.consumer_email or "").strip().lower() or None
                clean_state = (item.state or "").strip().upper() or "NY"
                clean_zip = (item.zip_code or "").strip() or None

                row = conn.execute(
                    insert_sql,
                    [
                        current_id,
                        date_rcvd,
                        item.product.strip() if item.product else "Checking or savings account",
                        item.sub_product.strip() if item.sub_product else None,
                        item.issue.strip() if item.issue else "Dispute reported",
                        item.sub_issue.strip() if item.sub_issue else None,
                        item.narrative.strip() if item.narrative else "Customer dispute details submitted via batch file.",
                        item.company.strip() if item.company else "JPMorgan Chase & Co.",
                        clean_state,
                        clean_zip,
                        "Bulk File Upload",
                        clean_email,
                        date_rcvd,
                    ],
                ).fetchone()
                created_list.append(row)
            conn.commit()
        return {"success": True, "count": len(created_list), "complaints": created_list}
    except Exception as exc:
        logger.exception("Error in batch complaint creation")
        raise HTTPException(status_code=500, detail=f"Failed to batch create complaints: {str(exc)}")


@router.put("/{complaint_id}/email")
def update_complaint_email(complaint_id: int, body: UpdateEmailIn):
    """Updates or adds the consumer email address for an existing complaint."""
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "UPDATE complaints SET consumer_email = %s WHERE complaint_id = %s "
                "RETURNING complaint_id, consumer_email",
                [body.consumer_email.lower().strip(), complaint_id],
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Complaint not found")
            return {"success": True, "consumer_email": row["consumer_email"]}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error updating complaint email")
        raise HTTPException(status_code=503, detail="Database error updating email.")


@router.post("/{complaint_id}/analysis")
def analyze_complaint(complaint_id: int, refresh: bool = False):
    """Classify and summarize one complaint with LLM, saving result in cache table."""
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT narrative, product, sub_product, issue, sub_issue "
                "FROM complaints WHERE complaint_id = %s",
                [complaint_id],
            ).fetchone()
            saved = conn.execute(
                "SELECT category, summary, model, basis FROM complaint_analysis "
                "WHERE complaint_id = %s",
                [complaint_id],
            ).fetchone()
    except Exception:
        logger.exception("Database error while reading complaint")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if saved and not refresh:
        return {"complaint_id": complaint_id, **saved, "cached": True}

    narrative = (row["narrative"] or "").strip()
    try:
        if narrative:
            basis = BASIS_NARRATIVE
            result = analyze_narrative(narrative)
        else:
            basis = BASIS_METADATA
            result = analyze_metadata(
                row["product"], row["sub_product"], row["issue"], row["sub_issue"]
            )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    model = settings.llm_model
    try:
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO complaint_analysis (complaint_id, category, summary, model, basis) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (complaint_id) DO UPDATE SET "
                "category = EXCLUDED.category, summary = EXCLUDED.summary, "
                "model = EXCLUDED.model, basis = EXCLUDED.basis, created_at = now()",
                [complaint_id, result["category"], result["summary"], model, basis],
            )
    except Exception:
        logger.exception("Database error while writing complaint analysis")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    return {"complaint_id": complaint_id, **result, "model": model, "basis": basis, "cached": False}


@router.get("/{complaint_id}/similar")
def similar_complaints(complaint_id: int, top_k: int = Query(3, ge=1, le=10)):
    """Finds historical precedent complaints with vector cosine similarity or category match."""
    try:
        with pool.connection() as conn:
            target = conn.execute(
                "SELECT product, issue, narrative FROM complaints WHERE complaint_id = %s",
                [complaint_id],
            ).fetchone()

            if not target:
                raise HTTPException(status_code=404, detail="Complaint not found")

            # Check if embedding exists in complaint_embeddings
            target_emb = conn.execute(
                "SELECT embedding FROM complaint_embeddings WHERE complaint_id = %s",
                [complaint_id],
            ).fetchone()

            # If embedding exists, use vector cosine distance
            if target_emb:
                sql = """
                    SELECT c.complaint_id, c.date_received, c.product, c.issue, c.company,
                           c.company_response_to_consumer, c.narrative,
                           ROUND((1 - (ce.embedding <=> %s::vector))::numeric, 3) AS similarity
                    FROM complaint_embeddings ce
                    JOIN complaints c ON c.complaint_id = ce.complaint_id
                    WHERE c.complaint_id != %s
                    ORDER BY ce.embedding <=> %s::vector
                    LIMIT %s;
                """
                vec_str = target_emb["embedding"]
                rows = conn.execute(sql, [vec_str, complaint_id, vec_str, top_k]).fetchall()
            else:
                sql = """
                    SELECT complaint_id, date_received, product, issue, company,
                           company_response_to_consumer, narrative, 0.75 as similarity
                    FROM complaints
                    WHERE complaint_id != %s AND (product = %s OR issue = %s)
                    ORDER BY date_received DESC
                    LIMIT %s;
                """
                rows = conn.execute(sql, [complaint_id, target["product"], target["issue"], top_k]).fetchall()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error retrieving similar complaints")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    return {"complaint_id": complaint_id, "similar": rows}


@router.post("/{complaint_id}/draft-reply")
def draft_complaint_reply(complaint_id: int, body: DraftReplyIn | None = None):
    """Draft an official bank reply letter for human approval using similar cases and regulation rules."""
    try:
        with pool.connection() as conn:
            complaint = conn.execute(
                "SELECT * FROM complaints WHERE complaint_id = %s", [complaint_id]
            ).fetchone()
            similar = conn.execute(
                "SELECT company_response_to_consumer FROM complaints "
                "WHERE product = %s AND complaint_id != %s AND company_response_to_consumer IS NOT NULL "
                "LIMIT 3",
                [complaint["product"], complaint_id],
            ).fetchall()
    except Exception:
        logger.exception("Database error while drafting reply")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    try:
        letter = draft_reply(complaint, similar)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {
        "complaint_id": complaint_id,
        "draft": letter,
        "model": settings.llm_model,
        "status": "ready_for_approval",
    }


@router.post("/{complaint_id}/request-approval")
def request_approval(
    complaint_id: int,
    body: RequestApprovalIn,
    request: Request,
    user=Depends(get_current_user),
):
    """Agent action: submits a drafted response for supervisor/admin approval and notifies supervisors."""
    user_name = user.get("full_name") or user.get("email")
    user_role = user.get("role", "agent")
    user_id = user.get("id")

    sql = """
        INSERT INTO complaint_responses (
            complaint_id, response_text, requested_by_id, requested_by_name, requested_by_role, status, requested_at
        ) VALUES (
            %s, %s, %s, %s, %s, 'pending_approval', now()
        )
        ON CONFLICT (complaint_id) DO UPDATE SET
            response_text = EXCLUDED.response_text,
            requested_by_id = EXCLUDED.requested_by_id,
            requested_by_name = EXCLUDED.requested_by_name,
            requested_by_role = EXCLUDED.requested_by_role,
            status = 'pending_approval',
            requested_at = now()
        RETURNING complaint_id, response_text, requested_by_name, requested_by_role, status, requested_at,
                  approved_by_name, approved_by_role, approved_at;
    """

    try:
        with pool.connection() as conn:
            complaint = conn.execute(
                "SELECT company, product, issue FROM complaints WHERE complaint_id = %s",
                [complaint_id]
            ).fetchone()
            if not complaint:
                raise HTTPException(status_code=404, detail="Complaint not found")

            row = conn.execute(
                sql,
                [complaint_id, body.response_text, user_id, user_name, user_role],
            ).fetchone()

            supervisors = conn.execute(
                "SELECT email, full_name FROM users WHERE role IN ('supervisor', 'admin') AND is_active = true"
            ).fetchall()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error while requesting approval")
        raise HTTPException(status_code=503, detail="Database error submitting response for approval.")

    # Dispatch email notification to all active supervisors
    client_origin = request.headers.get("origin")
    for sup in supervisors:
        try:
            send_supervisor_approval_request_email(
                to_email=sup["email"],
                supervisor_name=sup["full_name"],
                complaint_id=complaint_id,
                company=complaint.get("company") or "Bank",
                product=complaint.get("product") or "Service",
                issue=complaint.get("issue") or "Customer Dispute",
                agent_name=user_name,
                response_draft=body.response_text,
                client_origin=client_origin,
            )
        except Exception as mail_err:
            logger.warning(f"Could not notify supervisor {sup['email']}: {mail_err}")

    return row


@router.post("/{complaint_id}/approve")
def approve_response(
    complaint_id: int,
    body: ApproveResponseIn,
    request: Request,
    user=Depends(get_current_user),
):
    """Supervisor/Admin action: Approves resolution response and notifies consumer via email."""
    user_role = user.get("role", "agent")
    if user_role not in ("supervisor", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Access denied: Agents cannot approve responses directly. Please click 'Submit for Approval' to request supervisor approval.",
        )

    user_name = user.get("full_name") or user.get("email")
    user_id = user.get("id")

    sql = """
        INSERT INTO complaint_responses (
            complaint_id, response_text, approved_by_id, approved_by_name, approved_by_role, status, approved_at
        )
        VALUES (%s, %s, %s, %s, %s, 'approved', now())
        ON CONFLICT (complaint_id) DO UPDATE SET
            response_text = EXCLUDED.response_text,
            approved_by_id = EXCLUDED.approved_by_id,
            approved_by_name = EXCLUDED.approved_by_name,
            approved_by_role = EXCLUDED.approved_by_role,
            status = 'approved',
            approved_at = now()
        RETURNING complaint_id, response_text, approved_by_name, approved_by_role, status, approved_at,
                  requested_by_name, requested_by_role, requested_at;
    """

    try:
        with pool.connection() as conn:
            complaint = conn.execute(
                "SELECT complaint_id, product, issue, company, consumer_email FROM complaints WHERE complaint_id = %s",
                [complaint_id],
            ).fetchone()
            if not complaint:
                raise HTTPException(status_code=404, detail="Complaint not found")

            row = conn.execute(
                sql,
                [complaint_id, body.response_text, user_id, user_name, user_role],
            ).fetchone()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error while approving response")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    # Send email notification to consumer if email is available
    email_dispatched = False
    consumer_email = (complaint.get("consumer_email") or "").strip()
    if consumer_email:
        client_origin = request.headers.get("origin")
        try:
            email_dispatched = send_complaint_approval_email(
                consumer_email=consumer_email,
                complaint_id=complaint_id,
                product=complaint.get("product") or "Banking Service",
                issue=complaint.get("issue") or "Customer Dispute",
                company=complaint.get("company") or "Financial Institution",
                approver_name=user_name,
                approver_role=user_role,
                resolution_text=body.response_text,
                client_origin=client_origin,
            )
        except Exception as mail_exc:
            logger.warning(f"Failed to dispatch approval notification email to {consumer_email}: {mail_exc}")

    return {**row, "email_dispatched": email_dispatched, "consumer_email": consumer_email or None}


@router.post("/{complaint_id}/dispatch")
def dispatch_response(complaint_id: int, user=Depends(get_current_user)):
    """Marks an approved response as dispatched to the customer."""
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "UPDATE complaint_responses SET status = 'dispatched', dispatched_at = now() "
                "WHERE complaint_id = %s RETURNING complaint_id, status, dispatched_at, approved_by_name, approved_by_role",
                [complaint_id],
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="No approved response found for this complaint.")
            return row
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error while dispatching response")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")
