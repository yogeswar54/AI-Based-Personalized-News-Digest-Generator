from __future__ import annotations

from typing import Any

from app.services.preprocessing.text_cleaner import clean_html_text
from app.services.preprocessing.text_normalizer import normalize_text

MAX_COMPARISON_TEXT_LENGTH = 8000


def prepare_article_text(article: dict[str, Any]) -> str:
    if not isinstance(article, dict):
        raise ValueError("Article must be an object")

    parts = [
        article.get("processed_title") or article.get("title"),
        article.get("processed_description") or article.get("description"),
        article.get("content"),
    ]
    summary = article.get("summarization") or {}
    if summary.get("status") == "completed":
        parts.append(summary.get("short_summary"))

    unique_parts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not isinstance(part, str):
            continue
        cleaned = normalize_text(clean_html_text(part)).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            unique_parts.append(cleaned)
            seen.add(key)

    return " ".join(unique_parts)[:MAX_COMPARISON_TEXT_LENGTH]
