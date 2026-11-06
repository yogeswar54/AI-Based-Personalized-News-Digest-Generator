from __future__ import annotations

from datetime import datetime, timezone


class NewsArticle:
    def __init__(
        self,
        title: str,
        url: str,
        canonical_url: str,
        provider: str,
        source_name: str,
        category: str,
        description: str = "",
        content: str = "",
        image_url: str = "",
        author: str = "",
        external_id: str = "",
        provider_category: str = "",
        language: str = "en",
        country: str = "us",
        published_at: datetime | None = None,
        collected_at: datetime | None = None,
        updated_at: datetime | None = None,
        summarization: dict | None = None,
        embedding: list[float] | None = None,
        embedding_model: str | None = None,
        embedding_status: str = "pending",
        event_group_id: str | None = None,
        duplicate_detection_status: str = "pending",
        duplicate_checked_at: datetime | None = None,
    ) -> None:
        self.title = title.strip()
        self.url = url.strip()
        self.canonical_url = canonical_url.strip()
        self.provider = provider
        self.source_name = source_name.strip() or "Unknown Source"
        self.category = category
        self.description = description.strip()
        self.content = content.strip()
        self.image_url = image_url.strip()
        self.author = author.strip()
        self.external_id = external_id.strip() or self.canonical_url
        self.provider_category = provider_category.strip()
        self.language = language.strip() or "en"
        self.country = country.strip() or "us"
        self.published_at = published_at or datetime.now(timezone.utc)
        self.collected_at = collected_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or self.collected_at
        self.summarization = summarization or {
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
        }
        self.embedding = embedding
        self.embedding_model = embedding_model
        self.embedding_status = embedding_status
        self.event_group_id = event_group_id
        self.duplicate_detection_status = duplicate_detection_status
        self.duplicate_checked_at = duplicate_checked_at

    def to_document(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "image_url": self.image_url,
            "source": {
                "name": self.source_name,
                "url": "",
            },
            "author": self.author,
            "external_id": self.external_id,
            "provider": self.provider,
            "provider_category": self.provider_category,
            "category": self.category,
            "language": self.language,
            "country": self.country,
            "published_at": self.published_at,
            "collected_at": self.collected_at,
            "updated_at": self.updated_at,
            "summarization": self.summarization,
            "embedding": self.embedding,
            "embedding_model": self.embedding_model,
            "embedding_status": self.embedding_status,
            "event_group_id": self.event_group_id,
            "duplicate_detection_status": self.duplicate_detection_status,
            "duplicate_checked_at": self.duplicate_checked_at,
        }
