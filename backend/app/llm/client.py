import logging
from openai import OpenAI, OpenAIError
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """The AI model could not return an answer."""


_PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key": lambda: settings.groq_api_key,
    },
    "openai": {
        "base_url": None,
        "key": lambda: settings.openai_api_key,
    },
}

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        provider = settings.llm_provider.lower()
        if provider not in _PROVIDERS:
            raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use: {list(_PROVIDERS)}")
        config = _PROVIDERS[provider]
        api_key = config["key"]()
        if not api_key:
            raise LLMError(f"The API key for '{provider}' is not set in backend/.env")
        if not settings.llm_model:
            raise LLMError("LLM_MODEL is not set in backend/.env")

        _client = OpenAI(
            api_key=api_key,
            base_url=settings.llm_base_url or config["base_url"],
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )
    return _client


def chat(messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 700) -> str:
    """Send messages to the model and return its text response. Switchable via config."""
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except OpenAIError as exc:
        logger.exception("LLM call failed")
        raise LLMError("The AI service is temporarily unavailable. Please try again.") from exc

    text = response.choices[0].message.content
    if not text:
        raise LLMError("The AI returned an empty response.")
    return text.strip()
