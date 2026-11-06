from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx


class BaseNewsProvider(ABC):
    provider_name: str = "base"

    async def get_with_retries(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_attempts: int = 2,
    ) -> httpx.Response:
        for attempt in range(max_attempts):
            try:
                response = await client.get(url, params=params, headers=headers)
                if (response.status_code == 429 or response.status_code >= 500) and attempt + 1 < max_attempts:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response
            except httpx.TransportError:
                if attempt + 1 == max_attempts:
                    raise
                await asyncio.sleep(0.2 * (attempt + 1))
            except httpx.HTTPStatusError as exc:
                if (exc.response.status_code != 429 and exc.response.status_code < 500) or attempt + 1 == max_attempts:
                    raise
                await asyncio.sleep(0.2 * (attempt + 1))
        raise RuntimeError("HTTP request attempts exhausted")

    @abstractmethod
    async def fetch_articles(
        self,
        *,
        category: str | None = None,
        keyword: str | None = None,
        country: str | None = None,
        language: str | None = None,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch raw article records from a provider."""
