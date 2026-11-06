from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.config import get_settings
from app.database.mongodb import get_database
from app.services.deduplication.similarity_service import cosine_similarity

logger = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.IGNORECASE)
_STOP_WORDS = {
    "about", "after", "also", "amid", "and", "been", "before", "being",
    "for", "from", "have", "into", "more", "new", "news", "over", "report",
    "said", "story", "that", "the", "their", "there", "these", "they",
    "this", "through", "today", "under", "were", "what", "when", "which",
    "will", "with", "would",
}


def get_event_groups_collection():
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    collection = database["news_event_groups"]
    collection.create_index("article_ids")
    collection.create_index([("category", 1), ("updated_at", -1)])
    collection.create_index([("created_at", -1)])
    return collection


def _article_tokens(article: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(value)
        for value in (
            article.get("processed_title") or article.get("title") or "",
            article.get("processed_description") or article.get("description") or "",
            " ".join(article.get("keywords") or []),
        )
    ).lower()
    return {token for token in _TOKEN_RE.findall(text) if token not in _STOP_WORDS}


def _article_entities(article: dict[str, Any]) -> set[str]:
    summary_facts = (article.get("summarization") or {}).get("important_facts") or {}
    entities: set[str] = set()
    for field in ("people", "organizations", "locations", "dates", "numbers"):
        entities.update(
            str(value).strip().casefold()
            for value in summary_facts.get(field, [])
            if isinstance(value, str) and value.strip()
        )
    title = str(article.get("processed_title") or article.get("title") or "")
    entities.update(
        match.casefold()
        for match in re.findall(r"\b(?:[A-Z][\w'-]*\s+){0,2}[A-Z][\w'-]*\b", title)
        if len(match.strip()) > 2
    )
    return entities


def has_event_context_match(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_category = str(first.get("category") or "").casefold()
    second_category = str(second.get("category") or "").casefold()
    if first_category and second_category and first_category != second_category:
        return False

    first_tokens = _article_tokens(first)
    second_tokens = _article_tokens(second)
    common_tokens = first_tokens & second_tokens
    first_entities = _article_entities(first)
    second_entities = _article_entities(second)
    common_entities = first_entities & second_entities

    first_dates = set((first.get("summarization") or {}).get("important_facts", {}).get("dates", []))
    second_dates = set((second.get("summarization") or {}).get("important_facts", {}).get("dates", []))
    if first_dates and second_dates and not first_dates.intersection(second_dates):
        return False

    # Similarity alone is insufficient: require shared event wording or entities.
    return len(common_tokens) >= 2 or bool(common_entities)


def has_strong_event_context(first: dict[str, Any], second: dict[str, Any]) -> bool:
    if not has_event_context_match(first, second):
        return False
    common_entities = _article_entities(first) & _article_entities(second)
    common_tokens = _article_tokens(first) & _article_tokens(second)
    entity_tokens = {
        token
        for entity in common_entities
        for token in _TOKEN_RE.findall(entity)
    }
    event_tokens = common_tokens - entity_tokens
    first_dates = set((first.get("summarization") or {}).get("important_facts", {}).get("dates", []))
    second_dates = set((second.get("summarization") or {}).get("important_facts", {}).get("dates", []))
    same_date = bool(first_dates and second_dates and first_dates.intersection(second_dates))
    return same_date or (bool(common_entities) and bool(event_tokens)) or len(event_tokens) >= 3


def select_representative_article(articles: list[dict[str, Any]]) -> dict[str, Any]:
    if not articles:
        raise ValueError("At least one article is required to select a representative")

    def quality(article: dict[str, Any]) -> tuple[int, float]:
        score = 0
        if article.get("content"):
            score += 2
        if article.get("processed_description") or article.get("description"):
            score += 1
        if (article.get("summarization") or {}).get("status") == "completed":
            score += 2
        published_at = article.get("published_at")
        timestamp = published_at.timestamp() if isinstance(published_at, datetime) else 0.0
        return score, timestamp

    return max(articles, key=quality)


def find_best_group_match(article: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    settings = get_settings()
    best: dict[str, Any] | None = None
    for candidate in candidates:
        if candidate.get("_id") == article.get("_id"):
            continue
        if candidate.get("embedding_model") != article.get("embedding_model"):
            continue
        candidate_vector = candidate.get("embedding")
        article_vector = article.get("embedding")
        if not isinstance(candidate_vector, list) or not isinstance(article_vector, list):
            continue
        score = cosine_similarity(article_vector, candidate_vector)
        if score < settings.news_similarity_threshold:
            continue
        if score < settings.news_duplicate_threshold:
            if not has_strong_event_context(article, candidate):
                continue
        elif not has_event_context_match(article, candidate):
            continue
        candidate_group_id = candidate.get("event_group_id")
        if best is None or score > best["similarity"]:
            best = {
                "article": candidate,
                "group_id": candidate_group_id,
                "similarity": score,
                "confidence": "strong" if score >= settings.news_duplicate_threshold else "possible",
            }
    return best


def attach_article_to_group(article: dict[str, Any], group_id: ObjectId) -> dict[str, Any]:
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    articles = database["news_articles"]
    groups = get_event_groups_collection()
    article_id = article["_id"]
    existing_membership = articles.find_one(
        {"_id": article_id, "event_group_id": {"$exists": True, "$ne": None}}
    )
    if existing_membership:
        current_group = existing_membership.get("event_group_id")
        return {"group_id": current_group, "already_grouped": True}

    group = groups.find_one({"_id": group_id})
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event group not found")
    if article_id not in group.get("article_ids", []):
        groups.update_one(
            {"_id": group_id},
            {"$addToSet": {"article_ids": article_id}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        )
    articles.update_one(
        {"_id": article_id, "event_group_id": {"$in": [None]}},
        {"$set": {"event_group_id": group_id, "duplicate_detection_status": "completed", "duplicate_checked_at": datetime.now(timezone.utc)}},
    )
    all_ids = list(dict.fromkeys([*group.get("article_ids", []), article_id]))
    member_articles = list(articles.find({"_id": {"$in": all_ids}}))
    representative = select_representative_article(member_articles)
    groups.update_one(
        {"_id": group_id},
        {
            "$set": {
                "article_count": len(all_ids),
                "representative_article_id": representative["_id"],
                "event_title": representative.get("processed_title") or representative.get("title") or group.get("event_title"),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return {"group_id": group_id, "already_grouped": False}


def create_event_group(article: dict[str, Any]) -> ObjectId:
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    article_id = article["_id"]
    document = {
        "event_title": article.get("processed_title") or article.get("title") or "Related news coverage",
        "representative_article_id": article_id,
        "article_ids": [article_id],
        "category": article.get("category") or "World News",
        "keywords": list(dict.fromkeys(article.get("keywords") or []))[:20],
        "created_at": now,
        "updated_at": now,
        "article_count": 1,
    }
    result = get_event_groups_collection().insert_one(document)
    database["news_articles"].update_one(
        {"_id": article_id},
        {"$set": {"event_group_id": result.inserted_id, "duplicate_detection_status": "completed", "duplicate_checked_at": now}},
    )
    return result.inserted_id


def remove_article_from_group(article_id: ObjectId, group_id: ObjectId) -> None:
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    groups = get_event_groups_collection()
    group = groups.find_one({"_id": group_id})
    if not group or article_id not in group.get("article_ids", []):
        return
    groups.update_one(
        {"_id": group_id},
        {"$pull": {"article_ids": article_id}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    remaining_ids = [member_id for member_id in group.get("article_ids", []) if member_id != article_id]
    if not remaining_ids:
        groups.delete_one({"_id": group_id})
        return
    remaining_articles = list(database["news_articles"].find({"_id": {"$in": remaining_ids}}))
    representative = select_representative_article(remaining_articles)
    groups.update_one(
        {"_id": group_id},
        {
            "$set": {
                "article_ids": remaining_ids,
                "article_count": len(remaining_ids),
                "representative_article_id": representative["_id"],
                "event_title": representative.get("processed_title") or representative.get("title") or group.get("event_title"),
                "category": representative.get("category") or group.get("category"),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


def _serialize_group(group: dict[str, Any], articles: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    result = dict(group)
    result["id"] = str(result.pop("_id"))
    result["representative_article_id"] = str(result["representative_article_id"])
    result["article_ids"] = [str(article_id) for article_id in result.get("article_ids", [])]
    for timestamp in ("created_at", "updated_at"):
        if isinstance(result.get(timestamp), datetime):
            result[timestamp] = result[timestamp].isoformat()
    if articles is not None:
        result["articles"] = articles
    return result


def get_event_groups(
    *,
    category: str | None = None,
    keyword: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    groups = get_event_groups_collection()
    query: dict[str, Any] = {}
    if category:
        query["category"] = category
    if keyword:
        query["$or"] = [
            {"event_title": {"$regex": keyword, "$options": "i"}},
            {"keywords": {"$regex": keyword, "$options": "i"}},
        ]
    if start_date or end_date:
        query["updated_at"] = {}
        if start_date:
            query["updated_at"]["$gte"] = start_date
        if end_date:
            query["updated_at"]["$lte"] = end_date
    total = groups.count_documents(query)
    items = list(groups.find(query).sort("updated_at", -1).skip((page - 1) * limit).limit(limit))
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    from app.api.v1.news import serialize_article

    serialized_items = []
    for group in items:
        representative = database["news_articles"].find_one({"_id": group.get("representative_article_id")})
        serialized = _serialize_group(group)
        serialized["representative_article"] = serialize_article(representative) if representative else None
        serialized_items.append(serialized)
    return {"items": serialized_items, "page": page, "limit": limit, "total": total}


def get_event_group(group_id: str) -> dict[str, Any] | None:
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event group ID")
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    group = get_event_groups_collection().find_one({"_id": ObjectId(group_id)})
    if not group:
        return None
    articles = list(database["news_articles"].find({"_id": {"$in": group.get("article_ids", [])}}))
    articles.sort(key=lambda item: item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    from app.api.v1.news import serialize_article

    serialized = [serialize_article(article) for article in articles]
    return _serialize_group(group, serialized)


def get_related_articles(article_id: str) -> dict[str, Any]:
    if not ObjectId.is_valid(article_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid article ID")
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    article = database["news_articles"].find_one({"_id": ObjectId(article_id)})
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    group_id = article.get("event_group_id")
    if not group_id:
        return {"article_id": article_id, "items": []}
    group = get_event_groups_collection().find_one({"_id": group_id})
    if not group:
        logger.warning("Article %s refers to a missing event group", article_id)
        return {"article_id": article_id, "items": []}
    related = list(database["news_articles"].find({"_id": {"$in": group.get("article_ids", []), "$ne": article["_id"]}}))
    from app.api.v1.news import serialize_article

    for item in related:
        if article.get("embedding") and item.get("embedding"):
            try:
                item["similarity_score"] = cosine_similarity(article["embedding"], item["embedding"])
            except ValueError:
                item["similarity_score"] = None

    return {
        "article_id": article_id,
        "items": [
            {
                "article": serialize_article(item),
                "similarity": item.get("similarity_score"),
                "group_id": str(group_id),
            }
            for item in related
        ],
    }


def get_deduplication_stats() -> dict[str, int]:
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    articles = database["news_articles"]
    groups = get_event_groups_collection()
    total_articles = articles.count_documents({})
    with_embeddings = articles.count_documents({"embedding_status": "completed"})
    pending = articles.count_documents({"$or": [{"embedding_status": "pending"}, {"embedding_status": {"$exists": False}}]})
    failed = articles.count_documents({"embedding_status": "failed"})
    assigned = articles.count_documents({"event_group_id": {"$exists": True, "$ne": None}})
    return {
        "total_articles": total_articles,
        "articles_with_embeddings": with_embeddings,
        "pending_embedding_generation": pending,
        "failed_embedding_generation": failed,
        "total_event_groups": groups.count_documents({}),
        "articles_assigned_to_groups": assigned,
        "articles_not_yet_grouped": max(0, total_articles - assigned),
    }
