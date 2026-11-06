from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status

from app.services.news.news_collector import get_news_collection
from app.services.deduplication.news_grouping_service import (
    get_event_group as get_event_group_service,
    get_event_groups as get_event_groups_service,
    get_related_articles as get_related_articles_service,
)
from app.services.summarization.summarization_service import get_summary_for_article

router = APIRouter(prefix="/news", tags=["news"])


def serialize_article(article: dict[str, Any]) -> dict[str, Any]:
    payload = dict(article)
    payload.pop("embedding", None)
    payload.pop("embedding_error", None)
    payload.pop("duplicate_processing_started_at", None)
    for reference in ("event_group_id", "exact_duplicate_of"):
        if payload.get(reference) is not None:
            payload[reference] = str(payload[reference])
    payload["id"] = str(payload.pop("_id"))
    published_at = payload.get("published_at")
    if isinstance(published_at, datetime):
        payload["published_at"] = published_at.isoformat()
    collected_at = payload.get("collected_at")
    if isinstance(collected_at, datetime):
        payload["collected_at"] = collected_at.isoformat()
    updated_at = payload.get("updated_at")
    if isinstance(updated_at, datetime):
        payload["updated_at"] = updated_at.isoformat()
    for timestamp in ("preprocessed_at", "duplicate_checked_at"):
        value = payload.get(timestamp)
        if isinstance(value, datetime):
            payload[timestamp] = value.isoformat()
    summarization = payload.get("summarization")
    if isinstance(summarization, dict):
        summarization = dict(summarization)
        payload["summarization"] = summarization
        generated_at = summarization.get("generated_at")
        if isinstance(generated_at, datetime):
            summarization["generated_at"] = generated_at.isoformat()
        processing_started_at = summarization.get("processing_started_at")
        if isinstance(processing_started_at, datetime):
            summarization["processing_started_at"] = processing_started_at.isoformat()
    return payload


@router.get("")
async def list_news(
    category: str | None = Query(default=None),
    source: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    country: str | None = Query(default=None),
    language: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default="published_at"),
) -> dict[str, Any]:
    collection = get_news_collection()
    query: dict[str, Any] = {}

    if category:
        query["category"] = category
    if source:
        query["source.name"] = source
    if country:
        query["country"] = country
    if language:
        query["language"] = language
    if keyword:
        query["$or"] = [
            {"title": {"$regex": keyword, "$options": "i"}},
            {"description": {"$regex": keyword, "$options": "i"}},
            {"content": {"$regex": keyword, "$options": "i"}},
        ]

    if start_date or end_date:
        published_filter: dict[str, Any] = {}
        if start_date:
            published_filter["$gte"] = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        if end_date:
            published_filter["$lte"] = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        query["published_at"] = published_filter

    sort_direction = -1 if sort_by not in {"title", "source", "category"} else 1
    cursor = collection.find(query).sort(sort_by, sort_direction)
    total = collection.count_documents(query)
    items = list(cursor.skip((page - 1) * limit).limit(limit))

    return {
        "items": [serialize_article(item) for item in items],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": max(1, ceil(total / limit)) if total else 1,
    }


@router.get("/categories")
async def get_categories() -> dict[str, list[str]]:
    collection = get_news_collection()
    categories = sorted({item["category"] for item in collection.find({}, {"category": 1, "_id": 0}) if item.get("category")})
    return {"categories": categories}


@router.get("/sources")
async def get_sources() -> dict[str, list[str]]:
    collection = get_news_collection()
    sources = sorted({item for item in collection.distinct("source.name") if item})
    return {"sources": sources}


@router.get("/groups")
async def list_news_groups(
    category: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00")) if start_date else None
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00")) if end_date else None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date filter") from exc
    return get_event_groups_service(
        category=category,
        keyword=keyword,
        start_date=start,
        end_date=end,
        page=page,
        limit=limit,
    )


@router.get("/groups/{group_id}")
async def get_news_group(group_id: str) -> dict[str, Any]:
    group = get_event_group_service(group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event group not found")
    return group


@router.get("/{article_id}/related")
async def get_related_news(article_id: str) -> dict[str, Any]:
    return get_related_articles_service(article_id)


@router.get("/{article_id}/summary")
async def get_article_summary(article_id: str) -> dict[str, Any]:
    if not ObjectId.is_valid(article_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid article ID")

    article = get_news_collection().find_one({"_id": ObjectId(article_id)})
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    result = get_summary_for_article(article)
    result["article_id"] = article_id
    return result


@router.get("/{article_id}")
async def get_article(article_id: str) -> dict[str, Any]:
    if not ObjectId.is_valid(article_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid article ID")

    collection = get_news_collection()
    article = collection.find_one({"_id": ObjectId(article_id)})
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return serialize_article(article)
