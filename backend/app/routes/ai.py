from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.deps import get_current_user
from app.llm.client import LLMError, chat

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(get_current_user)])


class TestIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)


@router.post("/test")
def test_llm(body: TestIn):
    """Verifies that the LLM connection (Groq / OpenAI) is responsive."""
    try:
        answer = chat([{"role": "user", "content": body.prompt}])
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"provider": settings.llm_provider, "model": settings.llm_model, "answer": answer}
