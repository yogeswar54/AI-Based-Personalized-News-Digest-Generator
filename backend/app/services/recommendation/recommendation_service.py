from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.config import get_settings
from app.database.mongodb import get_database
from app.services.recommendation.ranking_service import rank_articles
from app.services.recommendation.relevance_scorer import score_article


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def get_recommendations_collection():
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    collection = database["news_articles"]
    collection.create_index([("published_at", -1), ("category", 1)])
    collection.create_index("event_group_id")
    return collection


def build_recommendations(
    user: dict[str, Any],
    *,
    category: str | None = None,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "relevance",
    now: datetime | None = None,
    excluded_article_ids: set[str] | None = None,
    excluded_group_ids: set[str] | None = None,
    repeat_after: datetime | None = None,
) -> dict[str, Any]:
    interests = user.get("interests") or []
    if not interests:
        return {
            "items": [],
            "page": page,
            "limit": limit,
            "total": 0,
            "interests": [],
            "message": "Select interests to receive personalized recommendations.",
        }

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    settings = get_settings()
    cutoff = current_time - timedelta(days=settings.recommendation_lookback_days)
    query: dict[str, Any] = {
        "exact_duplicate_of": {"$exists": False},
        "$or": [
            {"published_at": {"$gte": cutoff}},
            {"published_at": {"$exists": False}},
        ],
    }
    if category:
        query["category"] = category
    collection = get_recommendations_collection()
    candidates = list(
        collection.find(query).sort("published_at", -1).limit(settings.recommendation_candidate_limit)
    )

    group_ids = [article["event_group_id"] for article in candidates if article.get("event_group_id")]
    group_by_id: dict[ObjectId, dict[str, Any]] = {}
    database = get_database()
    if group_ids and database is not None:
        group_by_id = {
            group["_id"]: group
            for group in database["news_event_groups"].find({"_id": {"$in": group_ids}})
        }

    candidate_ids = set()
    for article in candidates:
        if not isinstance(article.get("title"), str) or not article["title"].strip():
            continue
        if not isinstance(article.get("url"), str) or not article["url"].strip():
            continue
        if article.get("preprocessing_status") == "failed":
            continue
        relevance = score_article(article, interests, now=current_time)
        if not relevance["matched_interests"]:
            continue
        published_at = relevance["published_at"]
        if published_at and (current_time - published_at).total_seconds() > settings.recommendation_lookback_days * 86400:
            continue
        candidate_ids.add(article["_id"])
    repeat_after_utc = _as_utc(repeat_after)
    for article in candidates:
        if not article.get("event_group_id"):
            continue
        group = group_by_id.get(article["event_group_id"])
        if group:
            article["_event_updated_at"] = group.get("updated_at")
        representative_id = group.get("representative_article_id") if group else None
        group_id_text = str(article.get("event_group_id"))
        if (
            group
            and group_id_text in (excluded_group_ids or set())
            and repeat_after_utc
            and _as_utc(group.get("updated_at"))
            and _as_utc(group["updated_at"]) > repeat_after_utc
        ):
            updated_members = [
                candidate for candidate in candidates
                if candidate.get("event_group_id") == article["event_group_id"]
                and _as_utc(candidate.get("published_at"))
                and _as_utc(candidate["published_at"]) > repeat_after_utc
            ]
            if updated_members:
                updated_members.sort(key=lambda candidate: _as_utc(candidate["published_at"]), reverse=True)
                representative_id = updated_members[0]["_id"]
        if representative_id in candidate_ids:
            if article["_id"] != representative_id:
                article["_is_nonrepresentative"] = True

    candidates = [article for article in candidates if not article.get("_is_nonrepresentative")]
    ranked = rank_articles(
        candidates,
        interests,
        now=current_time,
        limit=max(settings.recommendation_candidate_limit, (page + 1) * limit),
        excluded_article_ids=excluded_article_ids,
        excluded_group_ids=excluded_group_ids,
        repeat_after=repeat_after,
    )
    if sort_by == "published_at":
        ranked.sort(key=lambda item: item["published_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    elif sort_by == "category":
        ranked.sort(key=lambda item: (item["article"].get("category") or "", -item["relevance_score"]))
    total = len(ranked)

    from app.api.v1.news import serialize_article

    items = []
    for item in ranked[(page - 1) * limit : page * limit]:
        article = serialize_article(item["article"])
        group_id = item.get("event_group_id")
        group = group_by_id.get(group_id)
        items.append({
            "article": article,
            "event_group": {
                "id": str(group["_id"]),
                "title": group.get("event_title"),
                "article_count": group.get("article_count", 1),
            } if group else None,
            "relevance_score": item["relevance_score"],
            "reasons": item["reasons"],
        })
    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "interests": interests,
        "message": None,
    }
