import logging
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


@router.post("/ask")
def ask_regulation_rule(body: AskRuleIn):
    """Answers a banking rule question using Hybrid RAG (pgvector similarity + keyword/section matching + similarity threshold)."""
    import re
    question = body.question.strip()

    try:
        query_vector = embed_query(question)
    except Exception:
        logger.exception("Failed to generate query embedding")
        raise HTTPException(status_code=500, detail="Failed to process question vector.")

    # Extract potential regulation section numbers (e.g. '1005.11', '§ 1005.6', '1026.13')
    section_matches = re.findall(r"(?:§\s*)?(\d{4}\.\d+|[A-Z])", question)
    section_kw = f"%{section_matches[0]}%" if section_matches else "%__none__%"

    # Hybrid ranking: vector similarity + lexical boost for exact CFR section matches
    search_sql = """
        SELECT regulation_name, section, page_number, chunk_text,
               ROUND((1 - (embedding <=> %s::vector))::numeric, 4) AS similarity,
               CASE WHEN section ILIKE %s OR chunk_text ILIKE %s THEN 0.20 ELSE 0.0 END AS boost
        FROM regulation_chunks
        ORDER BY ((1 - (embedding <=> %s::vector)) + (CASE WHEN section ILIKE %s OR chunk_text ILIKE %s THEN 0.20 ELSE 0.0 END)) DESC
        LIMIT %s;
    """
    vector_str = f"[{','.join(str(v) for v in query_vector)}]"

    try:
        with pool.connection() as conn:
            chunks = conn.execute(
                search_sql,
                [vector_str, section_kw, section_kw, vector_str, section_kw, section_kw, body.top_k]
            ).fetchall()
    except Exception:
        logger.exception("Database error retrieving regulation chunks")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if not chunks:
        return {
            "question": question,
            "answer": "No regulation documents are currently indexed in the system.",
            "citations": [],
            "model": settings.llm_model,
        }

    # Strict similarity threshold check to prevent hallucinations when question is out-of-domain
    max_sim = max((float(c["similarity"]) for c in chunks), default=0.0)
    has_exact_match = any(float(c.get("boost", 0)) > 0 for c in chunks)
    min_threshold = settings.regulation_similarity_threshold

    if max_sim < min_threshold and not has_exact_match:
        return {
            "question": question,
            "answer": "I could not find sufficiently relevant provisions in the indexed federal banking regulations (Regulation E, Z, V, F) to answer this specific query. Please consult official regulatory publications or compliance counsel.",
            "citations": [],
            "model": settings.llm_model,
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
        "provider": settings.llm_provider,
    }
