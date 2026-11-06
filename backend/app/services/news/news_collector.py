from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.config import get_settings
from app.database.mongodb import get_database
from app.services.news.news_api_provider import NewsApiProvider
from app.services.news.news_normalizer import normalize_article
from app.services.news.rss_provider import RSSProvider

logger = logging.getLogger(__name__)


def get_news_collection():
    database = get_database()
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    collection = database["news_articles"]
    collection.create_index("canonical_url", unique=True, sparse=True)
    collection.create_index([("provider", 1), ("external_id", 1)])
    collection.create_index("published_at")
    collection.create_index("category")
    collection.create_index("source.name")
    collection.create_index("preprocessing_status")
    collection.create_index("classification_method")
    collection.create_index("preprocessed_at")
    collection.create_index("embedding_status")
    collection.create_index([("embedding_model", 1), ("embedding_status", 1)])
    collection.create_index([("category", 1), ("published_at", -1)])
    collection.create_index("event_group_id")
    return collection


def get_news_logs_collection():
    database = get_database()
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    collection = database["news_collection_logs"]
    collection.create_index("collected_at")
    return collection


def _matches_duplicate(collection: Any, article: dict[str, Any]) -> dict[str, Any] | None:
    canonical_url = article.get("canonical_url")
    provider = article.get("provider")
    external_id = article.get("external_id")
    filters: list[dict[str, Any]] = []
    if canonical_url:
        filters.append({"canonical_url": canonical_url})
    if provider and external_id:
        filters.append({"provider": provider, "external_id": external_id})
    if not filters:
        return None
    return collection.find_one({"$or": filters})


def _update_existing_article(collection: Any, existing: dict[str, Any], article: dict[str, Any]) -> bool:
    if existing is None:
        return False
    source_content_changed = any(
        existing.get(field) != article.get(field)
        for field in ("title", "description", "content", "provider_category")
    )
    updated_fields = {
        "title": article.get("title"),
        "description": article.get("description"),
        "content": article.get("content"),
        "url": article.get("url"),
        "canonical_url": article.get("canonical_url"),
        "image_url": article.get("image_url"),
        "source": article.get("source"),
        "author": article.get("author"),
        "provider": article.get("provider"),
        "provider_category": article.get("provider_category"),
        "language": article.get("language"),
        "country": article.get("country"),
        "published_at": article.get("published_at"),
        "updated_at": datetime.now(timezone.utc),
    }
    if source_content_changed:
        previous_group_id = existing.get("event_group_id")
        if previous_group_id is not None:
            from app.services.deduplication.news_grouping_service import remove_article_from_group

            remove_article_from_group(existing["_id"], previous_group_id)
        updated_fields.update(
            {
                "category": article.get("category"),
                "preprocessing_status": "pending",
                "preprocessing_error": None,
                "classification_method": None,
                "category_confidence": None,
                "processed_title": None,
                "processed_description": None,
                "keywords": [],
                "preprocessed_at": None,
                "embedding_status": "pending",
                "embedding_model": None,
                "embedding": None,
                "duplicate_detection_status": "pending",
                "duplicate_checked_at": None,
                "summarization": {
                    "status": "pending",
                    "source_used": None,
                    "short_summary": None,
                    "medium_summary": None,
                    "detailed_summary": None,
                    "key_points": [],
                    "important_facts": {
                        "people": [],
                        "organizations": [],
                        "locations": [],
                        "dates": [],
                        "numbers": [],
                    },
                    "model": None,
                    "generated_at": None,
                    "error": None,
                },
            }
        )
    update = {"$set": updated_fields}
    if source_content_changed:
        update["$unset"] = {
            "event_group_id": "",
            "similarity_score": "",
            "exact_duplicate_of": "",
            "duplicate_processing_started_at": "",
        }
    collection.update_one({"_id": existing["_id"]}, update)
    return True


async def collect_news(*, category: str | None = None, keyword: str | None = None, country: str | None = None, language: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    providers = [NewsApiProvider(), RSSProvider()]
    collection = get_news_collection()
    report = {
        "status": "success",
        "total_fetched": 0,
        "new_articles": 0,
        "duplicates_skipped": 0,
        "updated_articles": 0,
        "failed_articles": 0,
        "providers_processed": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    for provider in providers:
        try:
            provider_articles = await provider.fetch_articles(
                category=category,
                keyword=keyword,
                country=country,
                language=language,
                page_size=settings.news_collection_page_size,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("News provider '%s' failed", provider.provider_name)
            report["failed_articles"] += 1
            continue

        report["providers_processed"] += 1
        report["total_fetched"] += len(provider_articles)
        for raw_article in provider_articles:
            normalized = normalize_article(raw_article, provider.provider_name)
            if normalized is None:
                report["failed_articles"] += 1
                continue

            existing = _matches_duplicate(collection, normalized)
            if existing is not None:
                report["duplicates_skipped"] += 1
                if _update_existing_article(collection, existing, normalized):
                    report["updated_articles"] += 1
                continue

            try:
                collection.insert_one(normalized)
                report["new_articles"] += 1
            except DuplicateKeyError:
                report["duplicates_skipped"] += 1
            except Exception:
                logger.exception("Could not save collected article")
                report["failed_articles"] += 1

    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    try:
        logs_collection = get_news_logs_collection()
        logs_collection.insert_one(report)
    except HTTPException:
        logger.warning("News log collection unavailable; skipping collection log write")
    except Exception:  # pragma: no cover - defensive fallback
        logger.exception("Could not write news collection log")

    return report
