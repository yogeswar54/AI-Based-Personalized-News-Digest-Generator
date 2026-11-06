from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.services.news.base_provider import BaseNewsProvider

logger = logging.getLogger(__name__)


class NewsApiProvider(BaseNewsProvider):
    provider_name = "news_api"

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
        api_key = settings.news_api_key.strip()
        if not api_key:
            logger.warning("NEWS_API_KEY is not configured; skipping NewsAPI collection")
            return []

        params: dict[str, Any] = {
            "pageSize": min(max(page_size, 1), 100),
            "language": language or settings.news_api_default_language,
        }
        if country:
            params["country"] = country
        if category:
            params["category"] = category.lower()
        if keyword:
            params["q"] = keyword

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await self.get_with_retries(
                    client,
                    f"{settings.news_api_base_url}/top-headlines",
                    params=params,
                    headers={"X-Api-Key": api_key},
                )
                payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("NewsAPI request failed (%s)", type(exc).__name__)
            return []
        except ValueError:
            logger.warning("NewsAPI returned invalid JSON")
            return []

        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        normalized_articles: list[dict[str, Any]] = []
        for article in articles:
            if isinstance(article, dict):
                source = article.get("source") or {}
                article["source_name"] = source.get("name") if isinstance(source, dict) else source
                article["source_url"] = source.get("url") if isinstance(source, dict) else ""
                article["provider_category"] = article.get("category") or category or ""
                normalized_articles.append(article)
        return normalized_articles
