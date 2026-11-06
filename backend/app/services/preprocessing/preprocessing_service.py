from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.config import get_settings
from app.database.mongodb import get_database
from app.services.ai.gemini_classifier import classify_with_gemini
from app.services.preprocessing.keyword_extractor import extract_keywords
from app.services.preprocessing.text_cleaner import clean_html_text
from app.services.preprocessing.text_normalizer import normalize_text
from app.services.user_service import AVAILABLE_INTERESTS

logger = logging.getLogger(__name__)

_CATEGORY_KEYWORDS = {
    "Technology": ["technology", "software", "hardware", "cloud", "platform", "ai", "cyber", "internet"],
    "Artificial Intelligence": ["ai", "machine learning", "neural", "model", "automation", "llm", "algorithm"],
    "Business": ["business", "company", "market", "startup", "enterprise", "management", "retail"],
    "Finance": ["finance", "stock", "bank", "markets", "investment", "currency", "economy", "crypto"],
    "Sports": ["sports", "football", "basketball", "tennis", "league", "athlete", "match", "coach"],
    "Politics": ["politics", "government", "election", "policy", "parliament", "minister", "senate"],
    "Entertainment": ["entertainment", "movie", "music", "film", "streaming", "festival", "celebrity"],
    "Science": ["science", "research", "space", "biology", "physics", "study", "discovery"],
    "Health": ["health", "medical", "hospital", "wellness", "doctor", "nutrition", "vaccine"],
    "Education": ["education", "school", "student", "teacher", "university", "learning", "campus"],
    "Startups": ["startup", "founder", "venture", "funding", "scaleup", "investor", "launch"],
    "World News": ["world", "global", "international", "country", "diplomacy", "news"],
    "Environment": ["environment", "climate", "energy", "carbon", "sustainability", "weather"],
    "Automobile": ["automobile", "car", "vehicle", "tesla", "truck", "motor", "auto"],
    "Gaming": ["gaming", "game", "esports", "console", "player", "video game", "steam"],
}


def get_news_preprocessing_collection():
    database = get_database()
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    collection = database["news_articles"]
    collection.create_index("preprocessing_status")
    collection.create_index("classification_method")
    collection.create_index([("preprocessing_status", 1), ("published_at", -1)])
    return collection


def _valid_category(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned in AVAILABLE_INTERESTS:
        return cleaned
    for category in AVAILABLE_INTERESTS:
        if category.lower() == cleaned.lower():
            return category
    return None


def _rule_based_category(article: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
    text = " ".join(
        part
        for part in [
            article.get("processed_title") or article.get("title") or "",
            article.get("processed_description") or article.get("description") or "",
            article.get("provider_category") or article.get("category") or "",
            " ".join(keywords),
        ]
        if part
    ).lower()

    matches: dict[str, int] = {category: 0 for category in AVAILABLE_INTERESTS}
    for category, keywords_for_category in _CATEGORY_KEYWORDS.items():
        for keyword in keywords_for_category:
            if keyword in text:
                matches[category] += 1

    if not any(matches.values()):
        provider_category = _valid_category(article.get("provider_category") or article.get("category"))
        if provider_category:
            return {
                "category": provider_category,
                "confidence_score": 0.45,
                "classification_method": "provider_fallback",
                "keywords": keywords,
            }
        return {
            "category": "World News",
            "confidence_score": 0.12,
            "classification_method": "default",
            "keywords": keywords,
        }

    best_category, best_score = max(matches.items(), key=lambda item: item[1])
    if best_score <= 0:
        provider_category = _valid_category(article.get("provider_category") or article.get("category"))
        if provider_category:
            return {
                "category": provider_category,
                "confidence_score": 0.45,
                "classification_method": "provider_fallback",
                "keywords": keywords,
            }
        return {
            "category": "World News",
            "confidence_score": 0.12,
            "classification_method": "default",
            "keywords": keywords,
        }

    confidence = min(0.7, max(0.25, best_score / 3))
    return {
        "category": best_category,
        "confidence_score": round(confidence, 4),
        "classification_method": "rule_based",
        "keywords": keywords,
    }


async def classify_article(article: dict[str, Any]) -> dict[str, Any]:
    provider_category = _valid_category(article.get("provider_category") or article.get("category"))
    keywords = article.get("keywords") or extract_keywords(
        article.get("processed_title") or article.get("title"),
        article.get("processed_description") or article.get("description"),
    )

    try:
        ai_result = await classify_with_gemini(article)
        if ai_result.get("category") and _valid_category(ai_result.get("category")):
            return {
                **ai_result,
                "keywords": ai_result.get("keywords") or keywords,
                "category": _valid_category(ai_result.get("category")),
            }
    except ValueError:
        logger.warning("AI classification failed for article '%s'; falling back to provider or rule-based classification", article.get("title"))
    except Exception:  # pragma: no cover - defensive fallback
        logger.exception("Unexpected AI classification failure")

    if provider_category:
        return {
            "category": provider_category,
            "confidence_score": 0.55,
            "classification_method": "provider_fallback",
            "keywords": keywords,
        }

    rule_result = _rule_based_category(article, keywords)
    if rule_result.get("classification_method") == "default":
        return rule_result
    return rule_result


def _build_processed_title_and_description(article: dict[str, Any]) -> tuple[str, str]:
    title = clean_html_text(article.get("title") or "")
    description = clean_html_text(article.get("description") or "")
    if not title:
        title = clean_html_text(article.get("processed_title") or "")
    if not description:
        description = clean_html_text(article.get("processed_description") or "")
    if not title:
        title = "Untitled article"
    if not description:
        description = clean_html_text(article.get("content") or "")

    processed_title = normalize_text(title)[:250]
    processed_description = normalize_text(description)[:2000]
    return processed_title, processed_description


async def preprocess_article_document(article: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    if not isinstance(article, dict):
        raise ValueError("Article payload must be a dictionary")

    article_id = str(article.get("_id") or "")
    status = article.get("preprocessing_status")
    if not force and status == "completed":
        return {"status": "skipped", "article_id": article_id, "message": "Article already processed"}

    processed_title, processed_description = _build_processed_title_and_description(article)
    keywords = extract_keywords(processed_title, processed_description)

    article_for_classification = {
        "title": processed_title,
        "description": processed_description,
        "processed_title": processed_title,
        "processed_description": processed_description,
        "keywords": keywords,
        "category": article.get("category") or "World News",
        "provider_category": article.get("provider_category") or article.get("category") or "",
        "content": article.get("content") or "",
    }

    try:
        classification = await classify_article(article_for_classification)
        result = {
            "processed_title": processed_title,
            "processed_description": processed_description,
            "keywords": classification.get("keywords") or keywords,
            "category": classification.get("category") or "World News",
            "category_confidence": float(classification.get("confidence_score") or 0.0),
            "classification_method": classification.get("classification_method") or "default",
            "preprocessing_status": "completed",
            "preprocessed_at": datetime.now(timezone.utc),
            "preprocessing_error": None,
        }
        return {"status": "processed", "article_id": article_id, "result": result}
    except Exception as exc:  # pragma: no cover - defensive fallback
        error_message = str(exc)
        logger.exception("Preprocessing failed for article %s", article_id)
        return {
            "status": "failed",
            "article_id": article_id,
            "result": {
                "processed_title": processed_title,
                "processed_description": processed_description,
                "keywords": keywords,
                "category": article.get("category") or "World News",
                "category_confidence": 0.0,
                "classification_method": "default",
                "preprocessing_status": "failed",
                "preprocessed_at": None,
                "preprocessing_error": error_message,
            },
        }


def _query_pending_articles(retry_failed: bool = False) -> dict[str, Any]:
    if retry_failed:
        return {"$or": [{"preprocessing_status": "pending"}, {"preprocessing_status": "failed"}, {"preprocessing_status": {"$exists": False}}]}
    return {"$or": [{"preprocessing_status": "pending"}, {"preprocessing_status": {"$exists": False}}]}


async def preprocess_pending_articles(*, batch_size: int = 25, retry_failed: bool = False) -> dict[str, Any]:
    collection = get_news_preprocessing_collection()
    query = _query_pending_articles(retry_failed=retry_failed)
    cursor = collection.find(query).sort("published_at", -1).limit(max(1, batch_size))
    articles = list(cursor)

    report = {
        "status": "success",
        "total_candidates": len(articles),
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "retry_failed": retry_failed,
    }

    for article in articles:
        article_id = str(article.get("_id"))
        if article.get("preprocessing_status") == "completed" and not retry_failed:
            report["skipped"] += 1
            continue

        outcome = await preprocess_article_document(article, force=retry_failed)
        if outcome["status"] == "skipped":
            report["skipped"] += 1
            continue

        update_payload = outcome["result"]
        update_payload["updated_at"] = datetime.now(timezone.utc)
        collection.update_one({"_id": article["_id"]}, {"$set": update_payload})

        if outcome["status"] == "processed":
            report["processed"] += 1
        else:
            report["failed"] += 1

    return report


def get_preprocessing_stats() -> dict[str, Any]:
    collection = get_news_preprocessing_collection()
    total_articles = collection.count_documents({})
    processed_articles = collection.count_documents({"preprocessing_status": "completed"})
    pending_articles = collection.count_documents({"$or": [{"preprocessing_status": "pending"}, {"preprocessing_status": {"$exists": False}}]})
    failed_articles = collection.count_documents({"preprocessing_status": "failed"})
    ai_classified_articles = collection.count_documents({"classification_method": "ai"})
    fallback_classified_articles = collection.count_documents({"classification_method": {"$in": ["provider_fallback", "rule_based", "default"]}})

    return {
        "total_articles": total_articles,
        "processed_articles": processed_articles,
        "pending_articles": pending_articles,
        "failed_articles": failed_articles,
        "ai_classified_articles": ai_classified_articles,
        "fallback_classified_articles": fallback_classified_articles,
    }
