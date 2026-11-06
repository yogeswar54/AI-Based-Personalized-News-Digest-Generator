from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from app.services.user_service import AVAILABLE_INTERESTS

logger = logging.getLogger(__name__)

CATEGORY_ALIASES = {
    "technology": "Technology",
    "tech": "Technology",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "business": "Business",
    "finance": "Finance",
    "sports": "Sports",
    "politics": "Politics",
    "entertainment": "Entertainment",
    "science": "Science",
    "health": "Health",
    "education": "Education",
    "startups": "Startups",
    "startup": "Startups",
    "world": "World News",
    "world news": "World News",
    "environment": "Environment",
    "automobile": "Automobile",
    "autos": "Automobile",
    "gaming": "Gaming",
}


def normalize_article_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunparse(parsed._replace(fragment="")).rstrip("/") or None


def map_category(value: str | None) -> str:
    if not value:
        return "World News"
    cleaned = value.strip()
    key = cleaned.lower()
    if cleaned in AVAILABLE_INTERESTS:
        return cleaned
    if key in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[key]
    for category in AVAILABLE_INTERESTS:
        if category.lower() == key:
            return category
    return "World News"


def parse_published_at(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_article(raw_article: dict, provider_name: str) -> dict | None:
    if not isinstance(raw_article, dict):
        return None

    title = str(raw_article.get("title") or "").strip()
    url = str(raw_article.get("url") or raw_article.get("link") or "").strip()
    if not title or not url:
        return None

    source_info = raw_article.get("source")
    if isinstance(source_info, dict):
        source_name = str(source_info.get("name") or "Unknown Source").strip()
        source_url = str(source_info.get("url") or "").strip()
    else:
        source_name = str(raw_article.get("source_name") or raw_article.get("source") or "Unknown Source").strip()
        source_url = str(raw_article.get("source_url") or "").strip()

    if not source_name:
        source_name = "Unknown Source"

    canonical_url = normalize_article_url(raw_article.get("canonical_url") or raw_article.get("url") or raw_article.get("link"))
    if not canonical_url:
        canonical_url = normalize_article_url(url)
    if not canonical_url:
        return None

    description = raw_article.get("description") or raw_article.get("summary") or raw_article.get("snippet") or ""
    description_text = str(description).strip() if description else ""

    content = raw_article.get("content") or raw_article.get("body") or ""
    content_text = str(content).strip() if content else ""

    image_url = raw_article.get("image_url") or raw_article.get("image") or raw_article.get("urlToImage") or ""
    image_value = str(image_url).strip() if image_url else ""

    provider_category = raw_article.get("provider_category") or raw_article.get("category") or raw_article.get("topic") or ""
    category = map_category(str(provider_category).strip() if provider_category else "")

    published_at = parse_published_at(
        raw_article.get("published_at")
        or raw_article.get("publishedAt")
        or raw_article.get("published")
    )

    if published_at is None:
        published_at = datetime.now(timezone.utc)

    external_id = raw_article.get("external_id") or raw_article.get("id") or raw_article.get("guid") or raw_article.get("article_id") or canonical_url

    normalized = {
        "external_id": str(external_id),
        "title": title,
        "description": description_text,
        "content": content_text,
        "url": url,
        "canonical_url": canonical_url,
        "image_url": image_value,
        "source": {
            "name": source_name,
            "url": source_url,
        },
        "author": str(raw_article.get("author") or raw_article.get("author_name") or "").strip(),
        "provider": provider_name,
        "provider_category": str(provider_category).strip() if provider_category else "",
        "category": category,
        "language": str(raw_article.get("language") or raw_article.get("lang") or "en").strip() or "en",
        "country": str(raw_article.get("country") or raw_article.get("country_code") or "us").strip() or "us",
        "published_at": published_at,
        "collected_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "preprocessing_status": "pending",
        "preprocessing_error": None,
        "classification_method": None,
        "category_confidence": None,
        "processed_title": None,
        "processed_description": None,
        "keywords": [],
        "preprocessed_at": None,
        "embedding": None,
        "embedding_model": None,
        "embedding_status": "pending",
        "embedding_error": None,
        "event_group_id": None,
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
    return normalized
