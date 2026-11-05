import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db import pool
from app.deps import get_current_user
from app.llm.client import LLMError, chat
from app.llm.embedding import embed_query
from app.llm.prompts import (
    REGULATION_RAG_SYSTEM_PROMPT as SYSTEM_PROMPT,
    build_regulation_rag_user_prompt,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/regulations", tags=["regulations"], dependencies=[Depends(get_current_user)])


class AskRuleIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


@router.get("/usage")
def get_regulations_usage(user=Depends(get_current_user)):
    """Returns today's question usage and remaining quota for Ask the Rules."""
    super_admin = (settings.super_admin_email or "").strip().lower()
    is_super = bool(super_admin and user["email"].lower() == super_admin)
    is_pro = is_super or (user.get("plan") == "pro")

    if is_pro:
        return {
            "is_pro": True,
            "limit": None,
            "used": None,
            "remaining": None,
        }

    try:
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT query_count FROM user_ask_rules_usage WHERE user_id = %s AND usage_date = CURRENT_DATE",
                [user["id"]],
            ).fetchone()
            used = int(row["query_count"]) if row else 0
            return {
                "is_pro": False,
                "limit": 5,
                "used": used,
                "remaining": max(0, 5 - used),
            }
    except Exception:
        logger.exception("Failed to query user_ask_rules_usage")
        return {
            "is_pro": False,
            "limit": 5,
            "used": 0,
            "remaining": 5,
        }


@router.post("/ask")
def ask_regulation_rule(body: AskRuleIn, user=Depends(get_current_user)):
    """Answers a banking rule question using HNSW pgvector similarity + grounded LLM synthesis.
    Free tier accounts are limited to 5 questions per day; Pro tier has unlimited access.
    """
    super_admin = (settings.super_admin_email or "").strip().lower()
    is_super = bool(super_admin and user["email"].lower() == super_admin)
    is_pro = is_super or (user.get("plan") == "pro")

    current_count = 0
    if not is_pro:
        try:
            with pool.connection() as conn:
                row = conn.execute(
                    "SELECT query_count FROM user_ask_rules_usage WHERE user_id = %s AND usage_date = CURRENT_DATE",
                    [user["id"]],
                ).fetchone()
                current_count = int(row["query_count"]) if row else 0
        except Exception:
            logger.exception("Failed to query user_ask_rules_usage")
            current_count = 0

        if current_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="Daily question limit reached: Free tier accounts can ask up to 5 questions per day in Ask the Rules. Upgrade to Pro for unlimited questions.",
            )

    question = body.question.strip()

    try:
        query_vector = embed_query(question)
    except Exception:
        logger.exception("Failed to generate query embedding")
        raise HTTPException(status_code=500, detail="Failed to process question vector.")

    vector_str = f"[{','.join(str(v) for v in query_vector)}]"
    chunks = []

    # If user explicitly references a specific CFR section (e.g. '1005.11', '1026.13', '1022.43', '1006.6')
    section_match = re.search(r"\b(1005\.\d+|1026\.\d+|1022\.\d+|1006\.\d+)\b", question)

    search_sql = """
        SELECT regulation_name, section, page_number, chunk_text,
               ROUND((1 - (embedding <=> %s::vector))::numeric, 4) AS similarity
        FROM regulation_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """

    try:
        with pool.connection() as conn:
            # 1. If explicit section is requested, search within that section first
            if section_match:
                sec_code = section_match.group(1)
                sec_sql = """
                    SELECT regulation_name, section, page_number, chunk_text,
                           ROUND((1 - (embedding <=> %s::vector))::numeric, 4) AS similarity
                    FROM regulation_chunks
                    WHERE section ILIKE %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                """
                exact_chunks = conn.execute(
                    sec_sql,
                    [vector_str, f"%{sec_code}%", vector_str, body.top_k]
                ).fetchall()
                if exact_chunks:
                    chunks = exact_chunks

            # 2. Native HNSW cosine distance vector retrieval (O(log N) speed and optimal accuracy)
            if not chunks:
                chunks = conn.execute(search_sql, [vector_str, vector_str, body.top_k]).fetchall()
    except Exception:
        logger.exception("Database error retrieving regulation chunks")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    new_count = current_count + 1
    if not is_pro:
        try:
            with pool.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO user_ask_rules_usage (user_id, usage_date, query_count)
                    VALUES (%s, CURRENT_DATE, 1)
                    ON CONFLICT (user_id, usage_date)
                    DO UPDATE SET query_count = user_ask_rules_usage.query_count + 1;
                    """,
                    [user["id"]],
                )
        except Exception:
            logger.exception("Failed to update user_ask_rules_usage")

    usage_payload = {
        "is_pro": is_pro,
        "limit": None if is_pro else 5,
        "used": None if is_pro else new_count,
        "remaining": None if is_pro else max(0, 5 - new_count),
    }

    if not chunks:
        return {
            "question": question,
            "answer": "No regulation documents are currently indexed in the system.",
            "citations": [],
            "model": settings.llm_model,
            "usage": usage_payload,
        }

    # Similarity threshold: reject completely out-of-domain noise
    max_sim = max((float(c["similarity"]) for c in chunks), default=0.0)
    min_threshold = 0.35

    if max_sim < min_threshold and not section_match:
        return {
            "question": question,
            "answer": "I could not find sufficiently relevant provisions in the indexed federal banking regulations (Regulation E, Z, V, F) to answer this specific query. Please consult official regulatory publications or compliance counsel.",
            "citations": [],
            "model": settings.llm_model,
            "usage": usage_payload,
        }

    context_blocks = []
    citations = []

    for idx, c in enumerate(chunks, start=1):
        context_blocks.append(
            f"[Source {idx}]: {c['regulation_name']} | {c['section']} (Page {c['page_number']})\n{c['chunk_text']}"
        )
        citations.append({
            "source_id": idx,
            "regulation": c["regulation_name"],
            "section": c["section"],
            "page_number": c["page_number"],
            "similarity": float(c["similarity"]),
            "excerpt": c["chunk_text"][:300] + "...",
        })

    user_prompt = build_regulation_rag_user_prompt(question, context_blocks)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        answer = chat(messages, temperature=0.1, max_tokens=750)
    except LLMError:
        logger.exception("LLM error during regulation ask")
        raise HTTPException(status_code=503, detail="AI compliance service is temporarily unavailable. Please try again.")

    return {
        "question": question,
        "answer": answer,
        "citations": citations,
        "model": settings.llm_model,
        "usage": usage_payload,
    }
