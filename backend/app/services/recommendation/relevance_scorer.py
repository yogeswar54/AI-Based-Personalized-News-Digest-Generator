from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _normalized(value: Any) -> str:
    return " ".join(_WORD_RE.findall(str(value or "").casefold()))


def _published_at(article: dict[str, Any]) -> datetime | None:
    published = article.get("published_at")
    if isinstance(published, datetime):
        return published.replace(tzinfo=timezone.utc) if published.tzinfo is None else published.astimezone(timezone.utc)
    if isinstance(published, str):
        try:
            parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def score_article(article: dict[str, Any], interests: list[str], *, now: datetime | None = None) -> dict[str, Any]:
    settings = get_settings()
    normalized_interests = [(_normalized(item), item) for item in interests if _normalized(item)]
    category = _normalized(article.get("category"))
    keywords = [_normalized(item) for item in (article.get("keywords") or []) if _normalized(item)]
    searchable_text = _normalized(" ".join((
        str(article.get("processed_title") or article.get("title") or ""),
        str(article.get("processed_description") or article.get("description") or ""),
    )))

    matched_interests = [
        original for normalized, original in normalized_interests
        if normalized == category
    ]
    category_score = 1.0 if matched_interests else 0.0
    matched_keywords = [
        original for normalized, original in normalized_interests
        if normalized != category and (
            any(normalized == keyword or normalized in keyword or keyword in normalized for keyword in keywords)
            or normalized in searchable_text
        )
    ]
    keyword_score = min(1.0, len(matched_keywords) / max(1, len(normalized_interests)))

    timestamp = _published_at(article)
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (current_time.astimezone(timezone.utc) - timestamp).total_seconds() / 3600) if timestamp else 24 * 30
    recency_score = math.exp(-age_hours / 72) if timestamp else 0.0

    has_description = bool(str(article.get("processed_description") or article.get("description") or "").strip())
    has_content = bool(str(article.get("processed_content") or article.get("content") or "").strip())
    has_summary = (article.get("summarization") or {}).get("status") == "completed"
    content_score = (0.25 * has_description) + (0.35 * has_content) + (0.40 * has_summary)
    if article.get("preprocessing_status") == "completed":
        content_score = min(1.0, content_score + 0.1)

    weights = [
        settings.recommendation_category_weight,
        settings.recommendation_keyword_weight,
        settings.recommendation_recency_weight,
        settings.recommendation_content_weight,
    ]
    scores = [category_score, keyword_score, recency_score, content_score]
    weight_total = sum(weights)
    relevance = sum(score * weight for score, weight in zip(scores, weights)) / weight_total if weight_total else 0.0

    reasons: list[str] = []
    if matched_interests:
        reasons.append(f"Matches your {matched_interests[0]} interest")
    elif matched_keywords:
        reasons.append(f"Related to your {matched_keywords[0]} interest")
    if timestamp and age_hours <= 48:
        reasons.append("Recently published")
    if has_summary:
        reasons.append("Includes an AI-generated summary")
    elif has_description:
        reasons.append("Includes an article description")

    return {
        "relevance_score": round(max(0.0, min(1.0, relevance)), 4),
        "reasons": reasons,
        "category_score": category_score,
        "keyword_score": keyword_score,
        "recency_score": round(recency_score, 4),
        "content_score": round(content_score, 4),
        "matched_interests": matched_interests + matched_keywords,
        "published_at": timestamp,
    }
