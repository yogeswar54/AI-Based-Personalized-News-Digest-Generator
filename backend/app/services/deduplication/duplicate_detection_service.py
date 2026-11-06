from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.config import get_settings
from app.database.mongodb import get_database
from app.services.deduplication.embedding_service import generate_embeddings
from app.services.deduplication.news_grouping_service import (
    attach_article_to_group,
    create_event_group,
    find_best_group_match,
)
from app.services.deduplication.text_preparation import prepare_article_text
from app.services.news.news_normalizer import normalize_article_url

logger = logging.getLogger(__name__)


def get_news_deduplication_collection():
    database = get_database()
    if database is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    collection = database["news_articles"]
    collection.create_index("embedding_status")
    collection.create_index([("embedding_model", 1), ("embedding_status", 1)])
    collection.create_index([("category", 1), ("published_at", -1)])
    collection.create_index("event_group_id")
    return collection


def _find_exact_duplicate(collection: Any, article: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    canonical_url = normalize_article_url(article.get("canonical_url") or article.get("url"))
    if canonical_url:
        candidates.append({"canonical_url": canonical_url})
        candidates.append({"url": canonical_url})
    provider = article.get("provider")
    external_id = article.get("external_id")
    if provider and external_id:
        candidates.append({"provider": provider, "external_id": external_id})
    if not candidates:
        return None
    query: dict[str, Any] = {"$or": candidates}
    if article.get("_id") is not None:
        query["_id"] = {"$ne": article["_id"]}
    return collection.find_one(query)


def _eligible_query(retry_failed: bool, model_name: str) -> dict[str, Any]:
    statuses: list[dict[str, Any]] = [
        {"embedding_status": {"$exists": False}},
        {"embedding_status": "pending"},
        {"embedding_model": {"$ne": model_name}},
    ]
    if retry_failed:
        statuses.append({"embedding_status": "failed"})
    return {
        "preprocessing_status": "completed",
        "$or": statuses,
    }


def _candidate_query(article: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    settings = get_settings()
    published_at = article.get("published_at")
    if not isinstance(published_at, datetime):
        published_at = now
    return {
        "_id": {"$ne": article["_id"]},
        "embedding_status": "completed",
        "embedding_model": article["embedding_model"],
        "category": article.get("category") or "World News",
        "published_at": {
            "$gte": published_at - timedelta(days=settings.news_similarity_lookback_days),
            "$lte": published_at + timedelta(days=settings.news_similarity_lookback_days),
        },
    }


def _mark_failed(collection: Any, article_id: ObjectId, error: Exception) -> None:
    collection.update_one(
        {"_id": article_id},
        {
            "$set": {
                "embedding_status": "failed",
                "duplicate_detection_status": "failed",
                "embedding_error": "Embedding or similarity processing failed",
                "duplicate_checked_at": datetime.now(timezone.utc),
            }
        },
    )
    logger.warning("Duplicate detection failed for article %s: %s", article_id, type(error).__name__)


async def _process_article(collection: Any, article: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    article_id = article["_id"]
    model_name = settings.embedding_model_name
    article.update(
        {
            "embedding": embedding,
            "embedding_model": model_name,
            "embedding_status": "completed",
            "embedding_error": None,
        }
    )
    collection.update_one(
        {"_id": article_id, "duplicate_detection_status": "processing"},
        {
            "$set": {
                "embedding": embedding,
                "embedding_model": model_name,
                "embedding_status": "completed",
                "embedding_error": None,
            }
        },
    )

    candidates = list(
        collection.find(_candidate_query(article, now=now))
        .sort("published_at", -1)
        .limit(settings.news_similarity_candidate_limit)
    )
    match = find_best_group_match(article, candidates)
    if match is None:
        group_id = create_event_group(article)
        outcome = "unmatched"
        similarity = None
    else:
        group_id = match["group_id"]
        if group_id is None:
            group_id = create_event_group(match["article"])
        attach_article_to_group(article, group_id)
        similarity = match["similarity"]
        outcome = "grouped"

    update_fields: dict[str, Any] = {
        "duplicate_detection_status": "completed",
        "duplicate_checked_at": now,
        "event_group_id": group_id,
        "embedding_error": None,
    }
    if similarity is not None:
        update_fields["similarity_score"] = similarity
    collection.update_one({"_id": article_id}, {"$set": update_fields})
    return {
        "status": outcome,
        "article_id": str(article_id),
        "group_id": str(group_id),
        "similarity": similarity,
    }


async def detect_duplicates_for_article(article: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    if not isinstance(article, dict) or not isinstance(article.get("_id"), ObjectId):
        raise ValueError("A persisted article is required for duplicate detection")
    collection = get_news_deduplication_collection()
    settings = get_settings()
    model_name = settings.embedding_model_name
    article_id = article["_id"]
    if not force and article.get("duplicate_detection_status") == "completed" and article.get("embedding_model") == model_name:
        return {"status": "skipped", "article_id": str(article_id), "message": "Article was already checked"}

    now = datetime.now(timezone.utc)
    claim = collection.update_one(
        {
            "_id": article_id,
            "$or": [
                {"duplicate_detection_status": {"$exists": False}},
                {"duplicate_detection_status": {"$in": ["pending", "failed"]}},
                {"embedding_model": {"$ne": model_name}},
                {
                    "duplicate_detection_status": "processing",
                    "duplicate_processing_started_at": {"$lt": now - timedelta(minutes=30)},
                },
            ],
        },
        {
            "$set": {
                "duplicate_detection_status": "processing",
                "duplicate_processing_started_at": now,
            }
        },
    )
    if not claim.modified_count:
        current = collection.find_one({"_id": article_id}) or article
        current_status = current.get("duplicate_detection_status", "pending")
        return {"status": "skipped", "article_id": str(article_id), "message": f"Article is {current_status}"}

    try:
        exact_match = _find_exact_duplicate(collection, article)
        if exact_match:
            fields = {
                "duplicate_detection_status": "completed",
                "duplicate_checked_at": datetime.now(timezone.utc),
                "exact_duplicate_of": exact_match["_id"],
                "embedding_status": "skipped",
                "embedding_error": None,
            }
            if exact_match.get("event_group_id"):
                fields["event_group_id"] = exact_match["event_group_id"]
            collection.update_one({"_id": article_id}, {"$set": fields})
            return {
                "status": "exact_duplicate",
                "article_id": str(article_id),
                "duplicate_of": str(exact_match["_id"]),
            }

        text = prepare_article_text(article)
        if not text:
            collection.update_one(
                {"_id": article_id},
                {
                    "$set": {
                        "embedding_status": "skipped",
                        "duplicate_detection_status": "completed",
                        "duplicate_checked_at": datetime.now(timezone.utc),
                        "embedding_error": None,
                    }
                },
            )
            group_id = create_event_group(article)
            return {"status": "unmatched", "article_id": str(article_id), "group_id": str(group_id)}

        vector = (await asyncio.to_thread(generate_embeddings, [text]))[0]
        return await _process_article(collection, article, vector)
    except Exception as exc:
        _mark_failed(collection, article_id, exc)
        return {"status": "failed", "article_id": str(article_id), "message": "Duplicate detection failed"}


async def process_pending_articles(
    *,
    batch_size: int = 25,
    retry_failed: bool = False,
) -> dict[str, Any]:
    collection = get_news_deduplication_collection()
    settings = get_settings()
    model_name = settings.embedding_model_name
    query = _eligible_query(retry_failed, model_name)
    articles = list(
        collection.find(query)
        .sort("published_at", -1)
        .limit(max(1, min(batch_size, 200)))
    )
    report = {
        "status": "success",
        "total_candidates": len(articles),
        "processed": 0,
        "grouped": 0,
        "unmatched": 0,
        "exact_duplicates": 0,
        "failed": 0,
        "skipped": 0,
        "retry_failed": retry_failed,
    }
    to_embed: list[dict[str, Any]] = []
    texts: list[str] = []
    for article in articles:
        if article.get("duplicate_detection_status") == "processing":
            report["skipped"] += 1
            continue
        if article.get("duplicate_detection_status") == "completed" and article.get("embedding_model") == model_name:
            report["skipped"] += 1
            continue
        exact_match = _find_exact_duplicate(collection, article)
        if exact_match:
            collection.update_one(
                {"_id": article["_id"]},
                {"$set": {
                    "duplicate_detection_status": "completed",
                    "duplicate_checked_at": datetime.now(timezone.utc),
                    "exact_duplicate_of": exact_match["_id"],
                    "embedding_status": "skipped",
                }},
            )
            report["exact_duplicates"] += 1
            report["processed"] += 1
            continue
        text = prepare_article_text(article)
        if not text:
            result = await detect_duplicates_for_article(article)
            report["unmatched" if result["status"] == "unmatched" else "failed"] += 1
            report["processed"] += result["status"] == "unmatched"
            continue
        claim_time = datetime.now(timezone.utc)
        claim = collection.update_one(
            {
                "_id": article["_id"],
                "$or": [
                    {"duplicate_detection_status": {"$exists": False}},
                    {"duplicate_detection_status": {"$in": ["pending", "failed"]}},
                    {"embedding_model": {"$ne": model_name}},
                ],
            },
            {"$set": {"duplicate_detection_status": "processing", "duplicate_processing_started_at": claim_time}},
        )
        if not claim.modified_count:
            report["skipped"] += 1
            continue
        to_embed.append(article)
        texts.append(text)

    chunk_size = settings.news_embedding_batch_size
    for start in range(0, len(to_embed), chunk_size):
        chunk_articles = to_embed[start : start + chunk_size]
        chunk_texts = texts[start : start + chunk_size]
        try:
            embeddings = await asyncio.to_thread(generate_embeddings, chunk_texts)
        except Exception as exc:
            for article in chunk_articles:
                _mark_failed(collection, article["_id"], exc)
                report["failed"] += 1
            continue

        for article, embedding in zip(chunk_articles, embeddings):
            try:
                result = await _process_article(collection, article, embedding)
                report["processed"] += 1
                if result["status"] == "grouped":
                    report["grouped"] += 1
                elif result["status"] == "unmatched":
                    report["unmatched"] += 1
            except Exception as exc:
                _mark_failed(collection, article["_id"], exc)
                report["failed"] += 1
    return report
