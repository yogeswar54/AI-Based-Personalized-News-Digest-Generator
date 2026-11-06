from __future__ import annotations

from functools import lru_cache
import math
from typing import Sequence

from app.config import get_settings


@lru_cache(maxsize=1)
def _load_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Sentence-transformers is not installed; install backend requirements to enable deduplication"
        ) from exc
    return SentenceTransformer(model_name, device="cpu")


def generate_embeddings(texts: Sequence[str]) -> list[list[float]]:
    if not isinstance(texts, (list, tuple)):
        raise ValueError("Embedding input must be a sequence of strings")
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Embedding text must not be empty")
    if not texts:
        return []

    settings = get_settings()
    model = _load_model(settings.embedding_model_name)
    vectors = model.encode(
        list(texts),
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    if hasattr(vectors, "tolist"):
        vectors = vectors.tolist()
    if not isinstance(vectors, (list, tuple)) or len(vectors) != len(texts):
        raise ValueError("Embedding model returned invalid vectors")
    normalized: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, (list, tuple)) or not vector:
            raise ValueError("Embedding model returned invalid vectors")
        try:
            values = [float(value) for value in vector]
        except (TypeError, ValueError) as exc:
            raise ValueError("Embedding model returned invalid vectors") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Embedding model returned invalid vectors")
        normalized.append(values)
    if len({len(vector) for vector in normalized}) != 1:
        raise ValueError("Embedding model returned inconsistent vector dimensions")
    return normalized
