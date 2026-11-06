from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import get_settings
from app.services.recommendation.diversity_service import select_diverse_items
from app.services.recommendation.relevance_scorer import score_article


def rank_articles(
    articles: list[dict[str, Any]],
    interests: list[str],
    *,
    now: datetime | None = None,
    limit: int = 20,
    excluded_article_ids: set[str] | None = None,
    excluded_group_ids: set[str] | None = None,
    repeat_after: datetime | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    ranked: list[dict[str, Any]] = []
    for article in articles:
        if not isinstance(article.get("title"), str) or not article["title"].strip():
            continue
        if not isinstance(article.get("url"), str) or not article["url"].strip():
            continue
        scoring = score_article(article, interests, now=now)
        if not scoring["matched_interests"]:
            continue
        if article.get("preprocessing_status") == "failed":
            continue
        published_at = scoring["published_at"]
        if published_at and now:
            age_days = (now - published_at).total_seconds() / 86400
            if age_days > settings.recommendation_lookback_days:
                continue
        ranked.append({
            "article": article,
            "event_group_id": article.get("event_group_id"),
            "relevance_score": scoring["relevance_score"],
            "reasons": scoring["reasons"],
            "matched_interests": scoring["matched_interests"],
            "published_at": published_at,
            "event_updated_at": article.get("_event_updated_at"),
        })
    ranked.sort(key=lambda item: (
        item["relevance_score"],
        item["published_at"] or datetime.min.replace(tzinfo=now.tzinfo if now and now.tzinfo else None),
    ), reverse=True)
    return select_diverse_items(
        ranked,
        limit,
        excluded_article_ids=excluded_article_ids,
        excluded_group_ids=excluded_group_ids,
        repeat_after=repeat_after,
    )
