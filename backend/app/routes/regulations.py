import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db import pool
from app.deps import get_current_user
from app.llm.client import LLMError, chat
from app.llm.embedding import embed_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/regulations", tags=["regulations"], dependencies=[Depends(get_current_user)])


class AskRuleIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


SYSTEM_PROMPT = """You are an expert banking compliance assistant for a bank's complaint resolution team.
Your job is to answer compliance questions clearly and authoritatively based on official federal banking regulations.

Rules:
1. Base your answer strictly on the provided regulation excerpts. Do not invent rules.
2. State the relevant regulation name and section naturally in your explanation (e.g. Under Regulation E § 1005.11...).
3. Be concise, direct, and explain the exact rules, timeframes, deadlines, or customer rights in clean prose.
4. Do NOT output raw source citations, source numbers ([Source 1]), or page lists at the end. Focus 100% on providing clean, helpful regulatory information.
5. If the excerpts do not contain enough information, state:
   "The available regulation documents do not contain specific rules to answer this question."
"""


@router.post("/ask")
def ask_regulation_rule(body: AskRuleIn):
    """Answers a banking rule question using RAG (pgvector similarity + LLM grounded response)."""
    question = body.question.strip()

    try:
        query_vector = embed_query(question)
    except Exception as exc:
        logger.exception("Failed to generate query embedding")
        raise HTTPException(status_code=500, detail="Failed to process question vector.")

    search_sql = """
        SELECT regulation_name, section, page_number, chunk_text,
               ROUND((1 - (embedding <=> %s::vector))::numeric, 4) AS similarity
        FROM regulation_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """
    vector_str = f"[{','.join(str(v) for v in query_vector)}]"

    try:
        with pool.connection() as conn:
            chunks = conn.execute(search_sql, [vector_str, vector_str, body.top_k]).fetchall()
    except Exception:
        logger.exception("Database error retrieving regulation chunks")
        raise HTTPException(status_code=503, detail="Database is not available. Please try again.")

    if not chunks:
        return {
            "question": question,
            "answer": "No regulation documents are currently indexed in the system.",
            "citations": [],
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

    user_prompt = (
        f"Official Regulation Excerpts:\n\n"
        + "\n\n---\n\n".join(context_blocks)
        + f"\n\nEmployee Question: {question}\n\n"
        + "Please provide a direct, informative answer explaining the rule and requirements clearly."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        answer = chat(messages, temperature=0.1, max_tokens=700)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {
        "question": question,
        "answer": answer,
        "citations": citations,
        "model": settings.llm_model,
        "provider": settings.llm_provider,
    }
