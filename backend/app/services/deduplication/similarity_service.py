from __future__ import annotations

import math
from typing import Sequence


def cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    try:
        left = [float(value) for value in first]
        right = [float(value) for value in second]
    except (TypeError, ValueError) as exc:
        raise ValueError("Embeddings must contain numeric values") from exc
    if not left or not right:
        raise ValueError("Embeddings must be non-empty one-dimensional vectors")
    if len(left) != len(right):
        raise ValueError("Embedding dimensions do not match")
    if not all(math.isfinite(value) for value in left + right):
        raise ValueError("Embeddings must contain finite values")
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right)) / denominator))
