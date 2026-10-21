from fastembed import TextEmbedding
from app.core.config import settings

_embed_model: TextEmbedding | None = None


def get_embed_model() -> TextEmbedding:
    """Lazy load local embedding model singleton (BAAI/bge-small-en-v1.5, 384 dimensions)."""
    global _embed_model
    if _embed_model is None:
        _embed_model = TextEmbedding(model_name=settings.embedding_model)
    return _embed_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of text strings into a list of 384-dimensional float vectors."""
    model = get_embed_model()
    embeddings = list(model.embed(texts))
    return [e.tolist() if hasattr(e, "tolist") else list(e) for e in embeddings]


def embed_query(query: str) -> list[float]:
    """Embed a single query string into a 384-dimensional float vector."""
    return embed_texts([query])[0]
