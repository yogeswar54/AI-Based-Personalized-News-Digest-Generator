from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.services.news.news_collector import collect_news
from app.services.preprocessing.preprocessing_service import preprocess_pending_articles
from app.services.summarization.summarization_service import summarize_pending_articles
from app.services.deduplication.duplicate_detection_service import process_pending_articles
from app.services.digest.digest_service import generate_due_digests

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_news_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    settings = get_settings()
    collection_interval_minutes = max(1, settings.news_collection_interval_minutes)
    preprocessing_interval_minutes = max(1, settings.news_preprocessing_interval_minutes)
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        collect_news,
        trigger=IntervalTrigger(minutes=collection_interval_minutes),
        id="news_collection_job",
        replace_existing=True,
        misfire_grace_time=300,
        max_instances=1,
    )
    scheduler.add_job(
        preprocess_pending_articles,
        trigger=IntervalTrigger(minutes=preprocessing_interval_minutes),
        id="news_preprocessing_job",
        kwargs={"batch_size": settings.news_preprocessing_batch_size},
        replace_existing=True,
        misfire_grace_time=300,
        max_instances=1,
    )
    if settings.news_summarization_enabled:
        scheduler.add_job(
            summarize_pending_articles,
            trigger=IntervalTrigger(minutes=max(1, settings.news_summarization_interval_minutes)),
            id="news_summarization_job",
            kwargs={"batch_size": settings.news_summarization_batch_size},
            replace_existing=True,
            misfire_grace_time=300,
            max_instances=1,
        )
    if settings.news_deduplication_enabled:
        scheduler.add_job(
            process_pending_articles,
            trigger=IntervalTrigger(minutes=max(1, settings.news_deduplication_interval_minutes)),
            id="news_deduplication_job",
            kwargs={"batch_size": settings.news_deduplication_batch_size},
            replace_existing=True,
            misfire_grace_time=300,
            max_instances=1,
        )
        logger.info(
            "Automatic news deduplication enabled: every %s minutes (batch size %s)",
            settings.news_deduplication_interval_minutes,
            settings.news_deduplication_batch_size,
        )
    if settings.digest_scheduler_enabled:
        scheduler.add_job(
            generate_due_digests,
            trigger=IntervalTrigger(minutes=settings.digest_scheduler_interval_minutes),
            id="daily_digest_job",
            kwargs={"batch_size": settings.digest_scheduler_batch_size},
            replace_existing=True,
            misfire_grace_time=300,
            max_instances=1,
        )
        logger.info(
            "Daily digest scheduler enabled: checking opted-in users every %s minutes (batch size %s)",
            settings.digest_scheduler_interval_minutes,
            settings.digest_scheduler_batch_size,
        )
    enabled_jobs = ["collection", "preprocessing"]
    if settings.news_summarization_enabled:
        enabled_jobs.append("summarization")
    if settings.news_deduplication_enabled:
        enabled_jobs.append("deduplication")
    if settings.digest_scheduler_enabled:
        enabled_jobs.append("daily digest")
    logger.info(
        "Started news schedulers: %s (collection every %s minutes, preprocessing every %s minutes)",
        ", ".join(enabled_jobs),
        collection_interval_minutes,
        preprocessing_interval_minutes,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def shutdown_news_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
