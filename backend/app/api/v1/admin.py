from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.config import get_settings
from app.services.news.news_collector import collect_news
from app.services.preprocessing.preprocessing_service import (
    get_news_preprocessing_collection,
    get_preprocessing_stats,
    preprocess_article_document,
    preprocess_pending_articles,
)
from app.services.summarization.summarization_service import (
    generate_summary_for_article,
    get_news_summary_collection,
    get_summary_stats,
    summarize_pending_articles,
)
from app.services.deduplication.duplicate_detection_service import process_pending_articles
from app.services.deduplication.news_grouping_service import get_deduplication_stats
from app.services.digest.digest_service import get_digest_statistics

router = APIRouter(prefix="/admin", tags=["admin"])


async def ensure_admin_access(request: Request) -> None:
    admin_key = get_settings().admin_secret_key.strip()
    provided_key = request.headers.get("X-Admin-Key") or request.headers.get("x-admin-key")
    if not admin_key or provided_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization required. Set X-Admin-Key to the configured admin secret.",
        )


@router.post("/news/collect")
async def trigger_news_collection(request: Request) -> dict:
    await ensure_admin_access(request)
    return await collect_news()


@router.post("/news/preprocess")
async def trigger_news_preprocessing(
    request: Request,
    batch_size: int = Query(default=25, ge=1, le=200),
    retry_failed: bool = Query(default=False),
) -> dict:
    await ensure_admin_access(request)
    return await preprocess_pending_articles(batch_size=batch_size, retry_failed=retry_failed)


@router.post("/news/{article_id}/preprocess")
async def trigger_single_article_preprocessing(request: Request, article_id: str) -> dict:
    await ensure_admin_access(request)
    if not ObjectId.is_valid(article_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid article ID")
    collection = get_news_preprocessing_collection()
    article = collection.find_one({"_id": ObjectId(article_id)})
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    outcome = await preprocess_article_document(article, force=True)
    if outcome["status"] in {"processed", "failed"}:
        update_fields = dict(outcome["result"])
        update_fields["updated_at"] = datetime.now(timezone.utc)
        collection.update_one({"_id": article["_id"]}, {"$set": update_fields})
    return outcome


@router.post("/news/{article_id}/summarize")
async def trigger_single_article_summarization(
    request: Request,
    article_id: str,
    regenerate: bool = Query(default=False),
) -> dict:
    await ensure_admin_access(request)
    if not ObjectId.is_valid(article_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid article ID")
    collection = get_news_summary_collection()
    article = collection.find_one({"_id": ObjectId(article_id)})
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return await generate_summary_for_article(article, regenerate=regenerate)


@router.post("/news/summarize")
async def trigger_news_summarization(
    request: Request,
    batch_size: int = Query(default=10, ge=1, le=100),
    retry_failed: bool = Query(default=False),
    regenerate: bool = Query(default=False),
) -> dict:
    await ensure_admin_access(request)
    return await summarize_pending_articles(batch_size=batch_size, retry_failed=retry_failed, regenerate=regenerate)


@router.post("/news/deduplicate")
async def trigger_news_deduplication(
    request: Request,
    batch_size: int = Query(default=25, ge=1, le=200),
    retry_failed: bool = Query(default=False),
) -> dict:
    await ensure_admin_access(request)
    return await process_pending_articles(
        batch_size=batch_size,
        retry_failed=retry_failed,
    )


@router.get("/news/preprocessing/stats")
async def get_admin_preprocessing_stats(request: Request) -> dict:
    await ensure_admin_access(request)
    return get_preprocessing_stats()


@router.get("/news/summarization/stats")
async def get_admin_summarization_stats(request: Request) -> dict:
    await ensure_admin_access(request)
    return get_summary_stats()


@router.get("/news/deduplication/stats")
async def get_admin_deduplication_stats(request: Request) -> dict:
    await ensure_admin_access(request)
    return get_deduplication_stats()


@router.get("/digests/stats")
async def get_admin_digest_stats(request: Request) -> dict:
    await ensure_admin_access(request)
    return get_digest_statistics()
