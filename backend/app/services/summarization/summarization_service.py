from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import get_settings
from app.database.mongodb import get_database
from app.services.preprocessing.text_cleaner import clean_html_text
from app.services.summarization.summary_prompt import build_summary_prompt
from app.services.summarization.summary_validator import validate_summary_payload

logger = logging.getLogger(__name__)


def get_news_summary_collection():
    database = get_database()
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    collection = database["news_articles"]
    collection.create_index("summarization.status")
    collection.create_index("summarization.source_used")
    return collection


def _get_article_text(article: dict[str, Any]) -> tuple[str | None, str]:
    content = article.get("content") or ""
    processed_content = article.get("processed_content") or ""
    processed_description = article.get("processed_description") or article.get("description") or ""
    description = article.get("description") or ""

    if processed_content and str(processed_content).strip():
        return clean_html_text(str(processed_content)).strip() or None, "full_content"
    if content and str(content).strip():
        return clean_html_text(str(content)).strip() or None, "full_content"
    if processed_description and str(processed_description).strip():
        return clean_html_text(str(processed_description)).strip() or None, "description"
    if description and str(description).strip():
        return clean_html_text(str(description)).strip() or None, "description"
    return None, "none"


async def _generate_summary_payload(article: dict[str, Any], content: str) -> dict[str, Any]:
    settings = get_settings()
    api_key = (settings.gemini_api_key or settings.ai_api_key or "").strip()
    if not api_key:
        raise ValueError("Gemini API key is not configured")

    model_name = (settings.gemini_model or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    prompt = build_summary_prompt(
        article.get("processed_title") or article.get("title") or "Untitled article",
        content[: settings.news_summarization_max_input_chars],
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "short_summary": {"type": "STRING"},
                    "medium_summary": {"type": "STRING"},
                    "detailed_summary": {"type": "STRING"},
                    "key_points": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "important_facts": {
                        "type": "OBJECT",
                        "properties": {
                            "people": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "organizations": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "locations": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "dates": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "numbers": {"type": "ARRAY", "items": {"type": "STRING"}},
                        },
                        "required": ["people", "organizations", "locations", "dates", "numbers"],
                    },
                },
                "required": [
                    "short_summary",
                    "medium_summary",
                    "detailed_summary",
                    "key_points",
                    "important_facts",
                ],
            },
            "temperature": 0.3,
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, read=30.0)) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": api_key},
            )
            if response.status_code == 429:
                raise ValueError("AI summarization provider rate limit reached")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(
            "Gemini summarization request failed with status %s",
            getattr(exc.response, "status_code", "unknown"),
        )
        raise ValueError("Gemini summarization service is unavailable") from None

    try:
        body = response.json()
        candidate = body["candidates"][0]
        raw_text = candidate["content"]["parts"][0]["text"]
        parsed = json.loads(raw_text)
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning("Gemini returned malformed summary JSON")
        raise ValueError("Gemini returned malformed summary JSON") from None

    return validate_summary_payload(parsed)


async def generate_summary_for_article(article: dict[str, Any], *, regenerate: bool = False) -> dict[str, Any]:
    if not isinstance(article, dict):
        raise ValueError("Article payload must be a dictionary")

    article_id = article.get("_id")
    article_id_text = str(article_id or "")
    collection = get_news_summary_collection() if article_id is not None else None
    settings = get_settings()
    model_name = (settings.gemini_model or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    content, source_used = _get_article_text(article)
    now = datetime.now(timezone.utc)
    processing_data = {
        "status": "processing",
        "source_used": source_used,
        "short_summary": None,
        "medium_summary": None,
        "detailed_summary": None,
        "key_points": [],
        "important_facts": {"people": [], "organizations": [], "locations": [], "dates": [], "numbers": []},
        "model": model_name,
        "generated_at": None,
        "error": None,
        "processing_started_at": now,
    }
    if collection is not None:
        eligible_statuses = ["pending", "failed"]
        if regenerate:
            eligible_statuses.extend(["completed", "skipped"])
        claim_query = {
            "_id": article_id,
            "$or": [
                {"summarization.status": {"$exists": False}},
                {"summarization.status": {"$in": eligible_statuses}},
                {
                    "summarization.status": "processing",
                    "summarization.processing_started_at": {"$lt": now - timedelta(minutes=30)},
                },
            ],
        }
        claim = collection.update_one(
            claim_query,
            {"$set": {"summarization": processing_data, "updated_at": now}},
        )
        if not claim.modified_count:
            current = collection.find_one({"_id": article_id}) or article
            current_summary = current.get("summarization") or {}
            current_status = current_summary.get("status", "pending")
            return {
                "status": "skipped" if current_status == "completed" else current_status,
                "article_id": article_id_text,
                "summary": current_summary,
                "message": "Summary already exists" if current_status == "completed" else "Summarization is already in progress",
            }
    article["summarization"] = processing_data

    if not content:
        result = {
            **processing_data,
            "status": "skipped",
            "error": "No article content or description is available",
        }
        result.pop("processing_started_at", None)
        article["summarization"] = result
        if collection is not None:
            collection.update_one(
                {"_id": article_id, "summarization.status": "processing"},
                {"$set": {"summarization": result, "updated_at": datetime.now(timezone.utc)}},
            )
        return {"status": "skipped", "article_id": article_id_text, "result": result}

    try:
        payload = await _generate_summary_payload(article, content)
    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc) in {
            "Gemini API key is not configured",
            "Gemini summarization service is unavailable",
            "Gemini returned malformed summary JSON",
            "AI summarization provider rate limit reached",
        }:
            error_message = str(exc)
        else:
            error_message = "Summary generation failed; retry later"
        logger.warning("Summarization failed for article %s (%s)", article_id_text, error_message)
        error_payload = {
            "status": "failed",
            "source_used": source_used,
            "short_summary": None,
            "medium_summary": None,
            "detailed_summary": None,
            "key_points": [],
            "important_facts": {"people": [], "organizations": [], "locations": [], "dates": [], "numbers": []},
            "model": model_name,
            "generated_at": None,
            "error": error_message,
        }
        article["summarization"] = error_payload
        if collection is not None:
            collection.update_one(
                {"_id": article_id, "summarization.status": "processing"},
                {"$set": {"summarization": error_payload, "updated_at": datetime.now(timezone.utc)}},
            )
        return {"status": "failed", "article_id": article_id_text, "result": error_payload}

    result = {
        "status": "completed",
        **payload,
        "model": model_name,
        "source_used": source_used,
        "generated_at": datetime.now(timezone.utc),
        "error": None,
    }
    article["summarization"] = result
    if collection is not None:
        collection.update_one(
            {"_id": article_id, "summarization.status": "processing"},
            {"$set": {"summarization": result, "updated_at": datetime.now(timezone.utc)}},
        )
    return {"status": "processed", "article_id": article_id_text, "result": result}


def get_summary_for_article(article: dict[str, Any]) -> dict[str, Any]:
    summarization = article.get("summarization") or {}
    status = summarization.get("status")
    if status == "completed":
        return {"status": "completed", "summary": summarization}
    if status in {"pending", "processing", "failed", "skipped"}:
        return {"status": status, "summary": summarization}
    return {"status": "missing", "summary": None}


def _summary_query(retry_failed: bool = False, regenerate: bool = False) -> dict[str, Any]:
    statuses = ["pending"]
    if retry_failed or regenerate:
        statuses.append("failed")
    if regenerate:
        statuses.extend(["completed", "skipped"])
    return {
        "preprocessing_status": "completed",
        "$or": [
            {"summarization.status": {"$exists": False}},
            {"summarization.status": {"$in": statuses}},
        ],
    }


async def summarize_pending_articles(*, batch_size: int = 10, retry_failed: bool = False, regenerate: bool = False) -> dict[str, Any]:
    collection = get_news_summary_collection()
    cursor = collection.find(_summary_query(retry_failed=retry_failed, regenerate=regenerate)).sort("published_at", -1).limit(max(1, min(batch_size, 100)))
    articles = list(cursor)
    report = {
        "status": "success",
        "total_candidates": len(articles),
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "retry_failed": retry_failed,
        "regenerate": regenerate,
    }

    for article in articles:
        current_status = (article.get("summarization") or {}).get("status")
        if current_status == "completed" and not regenerate:
            report["skipped"] += 1
            continue

        result = await generate_summary_for_article(article, regenerate=regenerate)
        if result["status"] == "processed":
            report["processed"] += 1
        elif result["status"] in {"skipped", "processing", "pending"}:
            report["skipped"] += 1
        else:
            report["failed"] += 1

    return report


def get_summary_stats() -> dict[str, Any]:
    collection = get_news_summary_collection()
    total_articles = collection.count_documents({})
    completed_summaries = collection.count_documents({"summarization.status": "completed"})
    pending_summaries = collection.count_documents({"$or": [{"summarization.status": {"$exists": False}}, {"summarization.status": {"$in": ["pending", "processing"]}}]})
    failed_summaries = collection.count_documents({"summarization.status": "failed"})
    skipped_articles = collection.count_documents({"summarization.status": "skipped"})
    summaries_from_full_content = collection.count_documents(
        {"summarization.status": "completed", "summarization.source_used": "full_content"}
    )
    summaries_from_descriptions = collection.count_documents(
        {"summarization.status": "completed", "summarization.source_used": "description"}
    )

    return {
        "total_articles": total_articles,
        "completed_summaries": completed_summaries,
        "pending_summaries": pending_summaries,
        "failed_summaries": failed_summaries,
        "skipped_articles": skipped_articles,
        "summaries_from_full_content": summaries_from_full_content,
        "summaries_from_descriptions": summaries_from_descriptions,
    }
