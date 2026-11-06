from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

from app.config import get_settings
from app.database.mongodb import get_database
from app.schemas.digest import DigestSettings
from app.services.recommendation.recommendation_service import build_recommendations

logger = logging.getLogger(__name__)
DEFAULT_DIGEST_SETTINGS = DigestSettings().model_dump()


def get_digest_collection():
    database = get_database()
    if database is None:
        raise RuntimeError("Database unavailable")
    collection = database["user_daily_digests"]
    collection.create_index(
        [("user_id", 1), ("digest_date", 1), ("generation", 1)],
        unique=True,
    )
    collection.create_index(
        [("user_id", 1), ("digest_date", 1)],
        unique=True,
        partialFilterExpression={"is_current": True},
    )
    collection.create_index([("user_id", 1), ("generated_at", -1)])
    collection.create_index([("status", 1), ("generated_at", -1)])
    return collection


def get_digest_claims_collection():
    database = get_database()
    if database is None:
        raise RuntimeError("Database unavailable")
    collection = database["user_digest_generation_claims"]
    collection.create_index([("user_id", 1), ("digest_date", 1)], unique=True)
    collection.create_index("lease_until", expireAfterSeconds=0)
    return collection


def get_digest_scheduler_state_collection():
    database = get_database()
    if database is None:
        raise RuntimeError("Database unavailable")
    return database["digest_scheduler_state"]


def _get_next_enabled_users(database: Any, limit: int) -> list[dict[str, Any]]:
    state = get_digest_scheduler_state_collection()
    cursor_id = state.find_one({"_id": "daily_digest_user_cursor"})
    last_user_id = cursor_id.get("last_user_id") if cursor_id else None
    query: dict[str, Any] = {"digest_settings.digest_enabled": True}
    if last_user_id is not None:
        query["_id"] = {"$gt": last_user_id}

    users = list(database["users"].find(query).sort("_id", 1).limit(limit))
    if len(users) < limit and last_user_id is not None:
        first_batch = list(
            database["users"].find({"digest_settings.digest_enabled": True})
            .sort("_id", 1)
            .limit(limit - len(users))
        )
        selected_ids = {user["_id"] for user in users}
        users.extend(user for user in first_batch if user["_id"] not in selected_ids)

    if users:
        state.update_one(
            {"_id": "daily_digest_user_cursor"},
            {"$set": {"last_user_id": users[-1]["_id"], "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    return users


def user_digest_settings(user: dict[str, Any]) -> dict[str, Any]:
    try:
        return DigestSettings.model_validate({
            **DEFAULT_DIGEST_SETTINGS,
            **(user.get("digest_settings") or {}),
        }).model_dump()
    except Exception:
        logger.warning("Invalid stored digest settings for user %s; using defaults", user.get("_id"))
        return DEFAULT_DIGEST_SETTINGS.copy()


def local_digest_date(user: dict[str, Any], now: datetime | None = None) -> date:
    settings = user_digest_settings(user)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(ZoneInfo(settings["timezone"])).date()


def serialize_digest(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    result = dict(document)
    result["id"] = str(result.pop("_id"))
    result["user_id"] = str(result["user_id"])
    for field in ("generated_at", "updated_at"):
        if isinstance(result.get(field), datetime):
            result[field] = result[field].isoformat()
    for section in result.get("sections", []):
        for item in section.get("articles", []):
            if isinstance(item.get("published_at"), datetime):
                item["published_at"] = item["published_at"].isoformat()
    return result


def _fallback_introduction(sections: list[dict[str, Any]]) -> str:
    categories = [section["category"] for section in sections]
    if not categories:
        return "There are no matching stories in your digest today. Check back as new news is processed."
    if len(categories) == 1:
        return f"Here are today's selected stories about {categories[0]}."
    return f"Here are today's selected stories about {', '.join(categories[:-1])} and {categories[-1]}."


async def generate_digest_introduction(sections: list[dict[str, Any]]) -> str:
    fallback = _fallback_introduction(sections)
    stories = [
        f"- [{item['category']}] {article['title']}: {article['summary']}"
        for item in sections
        for article in item["articles"]
    ]
    if not stories:
        return fallback
    settings = get_settings()
    api_key = (settings.gemini_api_key or settings.ai_api_key or "").strip()
    if not api_key:
        return fallback
    prompt = (
        "Write one concise, simple-English introduction (at most 45 words) for this user's daily news digest. "
        "Use only facts and topics in these selected story titles and summaries. Do not add facts, predictions, "
        "or claims. Return only the introduction.\n\n" + "\n".join(stories)[:8000]
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, read=20.0)) as client:
            response = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 100},
                },
                headers={"x-goog-api-key": api_key},
            )
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text:
                return " ".join(text.split()[:45])[:500]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        logger.warning("Gemini digest introduction failed; using deterministic fallback")
    return fallback


def _recent_digest_exclusions(
    collection: Any,
    user_id: ObjectId,
    digest_date: str,
) -> tuple[set[str], set[str], datetime | None]:
    window = get_settings().digest_repeat_exclusion_days
    if window <= 0:
        return set(), set(), None
    start_date = (date.fromisoformat(digest_date) - timedelta(days=window)).isoformat()
    recent = list(collection.find({
        "user_id": user_id,
        "digest_date": {"$gte": start_date, "$lt": digest_date},
        "status": "completed",
    }).sort("generated_at", -1))
    article_ids: set[str] = set()
    group_ids: set[str] = set()
    latest_generated = None
    for digest in recent:
        generated_at = digest.get("generated_at")
        if isinstance(generated_at, datetime) and (latest_generated is None or generated_at > latest_generated):
            latest_generated = generated_at
        for section in digest.get("sections", []):
            for article in section.get("articles", []):
                if article.get("article_id"):
                    article_ids.add(str(article["article_id"]))
                if article.get("event_group_id"):
                    group_ids.add(str(article["event_group_id"]))
    return article_ids, group_ids, latest_generated


def _build_sections(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections_by_category: dict[str, list[dict[str, Any]]] = {}
    for recommendation in recommendations:
        article = recommendation["article"]
        category = article.get("category") or "World News"
        summary = (article.get("summarization") or {}).get("short_summary")
        if not summary:
            summary = article.get("processed_description") or article.get("description") or ""
        if not summary:
            summary = "Summary is not available; read the original article for details."
        sections_by_category.setdefault(category, []).append({
            "article_id": article["id"],
            "event_group_id": article.get("event_group_id"),
            "title": article["title"],
            "summary": summary,
            "source": (article.get("source") or {}).get("name") or "Unknown source",
            "url": article.get("url"),
            "image_url": article.get("image_url"),
            "published_at": article.get("published_at"),
            "relevance_score": recommendation["relevance_score"],
            "reasons": recommendation["reasons"],
        })
    return [
        {"category": category, "articles": articles}
        for category, articles in sorted(sections_by_category.items())
        if articles
    ]


def _claim_generation(user_id: ObjectId, digest_date: str) -> ObjectId | None:
    claims = get_digest_claims_collection()
    now = datetime.now(timezone.utc)
    token = ObjectId()
    settings = get_settings()
    claim_id = f"{user_id}:{digest_date}"
    try:
        claims.find_one_and_update(
            {
                "_id": claim_id,
                "$or": [
                    {"lease_until": {"$lte": now}},
                    {"lease_until": {"$exists": False}},
                ],
            },
            {"$set": {
                "user_id": user_id,
                "digest_date": digest_date,
                "token": token,
                "lease_until": now + timedelta(minutes=settings.digest_generation_lease_minutes),
            }},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        return None
    return token


async def generate_digest_for_user(
    user: dict[str, Any],
    *,
    regenerate: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    user_id = user.get("_id")
    if not isinstance(user_id, ObjectId):
        raise ValueError("A persisted user is required to generate a digest")
    database = get_database()
    if database is None:
        raise RuntimeError("Database unavailable")
    digest_settings = user_digest_settings(user)
    digest_date = local_digest_date(user, now).isoformat()
    collection = get_digest_collection()
    current_query = {"user_id": user_id, "digest_date": digest_date, "is_current": True}
    existing = collection.find_one(current_query)
    if existing and existing.get("status") == "completed" and not regenerate:
        return {"status": "completed", "digest": serialize_digest(existing), "already_generated": True}

    token = _claim_generation(user_id, digest_date)
    if token is None:
        existing = collection.find_one(current_query)
        return {
            "status": "in_progress",
            "digest": serialize_digest(existing),
            "message": "Digest generation is already in progress.",
        }

    try:
        existing = collection.find_one(current_query)
        if existing and existing.get("status") == "completed" and not regenerate:
            return {"status": "completed", "digest": serialize_digest(existing), "already_generated": True}

        excluded_articles, excluded_groups, repeat_after = _recent_digest_exclusions(
            collection, user_id, digest_date
        )
        recommendation_result = build_recommendations(
            user,
            page=1,
            limit=digest_settings["articles_per_digest"],
            now=now,
            excluded_article_ids=excluded_articles,
            excluded_group_ids=excluded_groups,
            repeat_after=repeat_after,
        )
        sections = _build_sections(recommendation_result["items"])
        introduction = await generate_digest_introduction(sections)
        generated_at = datetime.now(timezone.utc)
        generation = collection.count_documents({"user_id": user_id, "digest_date": digest_date}) + 1
        document = {
            "user_id": user_id,
            "digest_date": digest_date,
            "timezone": digest_settings["timezone"],
            "generation": generation,
            "is_current": False,
            "title": "Your Daily News Digest",
            "introduction": introduction,
            "sections": sections,
            "total_articles": sum(len(section["articles"]) for section in sections),
            "generated_at": generated_at,
            "status": "completed",
            "created_at": generated_at,
        }
        result = collection.insert_one(document)
        collection.update_one(current_query, {"$set": {"is_current": False}})
        collection.update_one({"_id": result.inserted_id}, {"$set": {"is_current": True}})
        saved = collection.find_one({"_id": result.inserted_id})
        return {"status": "completed", "digest": serialize_digest(saved), "already_generated": False}
    except Exception:
        logger.exception("Daily digest generation failed for user %s on %s", user_id, digest_date)
        failed_at = datetime.now(timezone.utc)
        generation = collection.count_documents({"user_id": user_id, "digest_date": digest_date}) + 1
        failure = {
            "user_id": user_id,
            "digest_date": digest_date,
            "timezone": digest_settings["timezone"],
            "generation": generation,
            "is_current": False,
            "title": "Your Daily News Digest",
            "introduction": "",
            "sections": [],
            "total_articles": 0,
            "generated_at": failed_at,
            "status": "failed",
            "error": "Digest generation failed; retry later.",
            "created_at": failed_at,
        }
        collection.insert_one(failure)
        return {"status": "failed", "digest": None, "message": failure["error"]}
    finally:
        get_digest_claims_collection().delete_one({
            "_id": f"{user_id}:{digest_date}",
            "token": token,
        })


async def generate_due_digests(*, batch_size: int | None = None, now: datetime | None = None) -> dict[str, int]:
    database = get_database()
    if database is None:
        raise RuntimeError("Database unavailable")
    settings = get_settings()
    limit = batch_size or settings.digest_scheduler_batch_size
    users = _get_next_enabled_users(database, max(1, min(limit, 1000)))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    report = {"users_checked": len(users), "due": 0, "completed": 0, "failed": 0, "skipped": 0}
    for user in users:
        digest_preferences = user_digest_settings(user)
        local_now = current.astimezone(ZoneInfo(digest_preferences["timezone"]))
        requested_time = time.fromisoformat(digest_preferences["digest_time"])
        if local_now.time().replace(tzinfo=None) < requested_time:
            report["skipped"] += 1
            continue
        report["due"] += 1
        try:
            result = await generate_digest_for_user(user, now=current)
            if result["status"] == "completed":
                report["completed"] += 1
            elif result["status"] == "failed":
                report["failed"] += 1
            else:
                report["skipped"] += 1
        except Exception:
            report["failed"] += 1
            logger.exception("Scheduled digest generation failed for user %s", user.get("_id"))
    return report


def get_digest_statistics() -> dict[str, int]:
    database = get_database()
    if database is None:
        raise RuntimeError("Database unavailable")
    digests = get_digest_collection()
    enabled_users = database["users"].count_documents({"digest_settings.digest_enabled": True})
    completed = digests.count_documents({"status": "completed"})
    failed = digests.count_documents({"status": "failed"})
    articles_in_digests = sum(
        int(document.get("total_articles", 0))
        for document in digests.find({"status": "completed"}, {"total_articles": 1})
    )
    return {
        "total_generated_digests": completed + failed,
        "successful_digests": completed,
        "failed_digests": failed,
        "users_with_digest_enabled": enabled_users,
        "articles_in_digests": articles_in_digests,
    }


def get_user_digest(user_id: ObjectId, digest_id: str) -> dict[str, Any] | None:
    if not ObjectId.is_valid(digest_id):
        return None
    digest = get_digest_collection().find_one({
        "_id": ObjectId(digest_id),
        "user_id": user_id,
    })
    return serialize_digest(digest)


def get_user_digest_history(
    user_id: ObjectId,
    *,
    page: int = 1,
    limit: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {"user_id": user_id, "status": "completed"}
    date_range: dict[str, str] = {}
    if start_date:
        date.fromisoformat(start_date)
        date_range["$gte"] = start_date
    if end_date:
        date.fromisoformat(end_date)
        date_range["$lte"] = end_date
    if date_range:
        query["digest_date"] = date_range
    collection = get_digest_collection()
    total = collection.count_documents(query)
    documents = list(
        collection.find(query).sort([("digest_date", -1), ("generation", -1)])
        .skip((page - 1) * limit)
        .limit(limit)
    )
    return {
        "items": [serialize_digest(item) for item in documents],
        "page": page,
        "limit": limit,
        "total": total,
    }


def update_user_digest_settings(user_id: ObjectId, payload: DigestSettings) -> dict[str, Any]:
    database = get_database()
    if database is None:
        raise RuntimeError("Database unavailable")
    updated = payload.model_dump()
    result = database["users"].update_one(
        {"_id": user_id},
        {"$set": {"digest_settings": updated, "updated_at": datetime.now(timezone.utc)}},
    )
    if not result.matched_count:
        raise ValueError("User account not found")
    return updated


def get_today_digest(user: dict[str, Any]) -> dict[str, Any] | None:
    digest_date = local_digest_date(user).isoformat()
    digest = get_digest_collection().find_one({
        "user_id": user["_id"],
        "digest_date": digest_date,
        "is_current": True,
        "status": "completed",
    })
    return serialize_digest(digest)
