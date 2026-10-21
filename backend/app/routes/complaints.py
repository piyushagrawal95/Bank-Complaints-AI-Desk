import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db import pool
from app.deps import get_current_user
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
    "state, submitted_via, company_response_to_consumer, timely_response"
)


class DraftReplyIn(BaseModel):
    custom_instructions: str | None = Field(default=None, max_length=500)


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
        conditions.append("(issue ILIKE %s OR sub_issue ILIKE %s OR company ILIKE %s)")
        params.extend([f"%{q}%"] * 3)

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
                "SELECT response_text, approved_by_name, approved_by_role, status, approved_at, dispatched_at "
                "FROM complaint_responses WHERE complaint_id = %s",
                [complaint_id],
            ).fetchone()
    except Exception:
        logger.exception("Database error while reading complaint")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {**row, "analysis": analysis, "response": response}


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
        logger.exception("Database error while saving analysis")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    return {
        "complaint_id": complaint_id,
        **result,
        "model": model,
        "basis": basis,
        "cached": False,
    }


@router.get("/{complaint_id}/similar")
def get_similar_complaints(complaint_id: int, top_k: int = Query(3, ge=1, le=10)):
    """Find similar past complaints using vector search or semantic similarity."""
    try:
        with pool.connection() as conn:
            target = conn.execute(
                "SELECT complaint_id, product, issue, narrative FROM complaints WHERE complaint_id = %s",
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
                # Fallback to product & issue keyword similarity if embeddings not yet indexed
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


class ApproveResponseIn(BaseModel):
    response_text: str = Field(min_length=10)


@router.post("/{complaint_id}/approve")
def approve_response(
    complaint_id: int,
    body: ApproveResponseIn,
    user=Depends(get_current_user),
):
    """Saves the human-approved response letter to the database audit record."""
    user_name = user.get("full_name") or user.get("email")
    user_role = user.get("role", "agent")
    user_id = user.get("id")

    sql = """
        INSERT INTO complaint_responses (complaint_id, response_text, approved_by_id, approved_by_name, approved_by_role, status, approved_at)
        VALUES (%s, %s, %s, %s, %s, 'approved', now())
        ON CONFLICT (complaint_id) DO UPDATE SET
            response_text = EXCLUDED.response_text,
            approved_by_id = EXCLUDED.approved_by_id,
            approved_by_name = EXCLUDED.approved_by_name,
            approved_by_role = EXCLUDED.approved_by_role,
            status = 'approved',
            approved_at = now()
        RETURNING complaint_id, response_text, approved_by_name, approved_by_role, status, approved_at;
    """

    try:
        with pool.connection() as conn:
            exists = conn.execute("SELECT 1 FROM complaints WHERE complaint_id = %s", [complaint_id]).fetchone()
            if not exists:
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

    return row


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

