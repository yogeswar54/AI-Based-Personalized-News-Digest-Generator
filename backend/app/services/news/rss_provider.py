from __future__ import annotations

import logging
from typing import Any

import feedparser
import httpx

from app.config import get_settings
from app.services.news.base_provider import BaseNewsProvider

logger = logging.getLogger(__name__)


class RSSProvider(BaseNewsProvider):
    provider_name = "rss"

    async def fetch_articles(
        self,
        *,
        category: str | None = None,
        keyword: str | None = None,
        country: str | None = None,
        language: str | None = None,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        settings = get_settings()
        items: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for feed_url in settings.rss_feed_urls:
                if not feed_url.strip():
                    continue
                try:
                    response = await self.get_with_retries(client, feed_url)
                    parsed_feed = feedparser.parse(response.content)
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("RSS feed failed to fetch or parse (%s)", type(exc).__name__)
                    continue
                if getattr(parsed_feed, "bozo", False) and parsed_feed.get("bozo_exception"):
                    logger.warning("RSS feed is invalid (%s)", type(parsed_feed.get("bozo_exception")).__name__)
                    continue

                for entry in parsed_feed.entries[:page_size]:
                    link = getattr(entry, "link", "") or ""
                    title = getattr(entry, "title", "") or ""
                    if not link or not title:
                        continue
                    content = getattr(entry, "content", None) or []
                    item = {
                        "title": title,
                        "url": link,
                        "link": link,
                        "description": getattr(entry, "summary", "") or getattr(entry, "description", "") or "",
                        "content": content[0].get("value", "") if content else "",
                        "image_url": getattr(entry, "image", "") or "",
                        "source_name": getattr(parsed_feed.feed, "title", "") or "RSS Feed",
                        "source_url": getattr(parsed_feed.feed, "link", "") or "",
                        "provider_category": category or "",
                        "published_at": getattr(entry, "published", "") or getattr(entry, "updated", "") or "",
                        "author": getattr(entry, "author", "") or "",
                        "language": language or "en",
                        "country": country or settings.news_api_default_country,
                    }
                    if keyword and keyword.lower() not in (title.lower() + " " + (item["description"] or "")).lower():
                        continue
                    items.append(item)
        return items
