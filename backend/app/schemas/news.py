from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImportantFacts(BaseModel):
    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)


class ArticleSummarization(BaseModel):
    status: Literal["pending", "processing", "completed", "failed", "skipped"]
    short_summary: str | None = None
    medium_summary: str | None = None
    detailed_summary: str | None = None
    key_points: list[str] = Field(default_factory=list)
    important_facts: ImportantFacts = Field(default_factory=ImportantFacts)
    model: str | None = None
    source_used: str | None = None
    generated_at: datetime | None = None
    error: str | None = None


class NewsArticleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = ""
    content: str = ""
    url: str = Field(..., min_length=1)
    canonical_url: str = Field(..., min_length=1)
    image_url: str = ""
    source: dict[str, str] = Field(default_factory=lambda: {"name": "", "url": ""})
    author: str = ""
    provider: str = ""
    provider_category: str = ""
    category: str = "World News"
    language: str = "en"
    country: str = "us"
    published_at: datetime | None = None
    collected_at: datetime | None = None
    updated_at: datetime | None = None
    processed_title: str | None = None
    processed_description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    category_confidence: float | None = None
    classification_method: str | None = None
    preprocessing_status: str = "pending"
    preprocessed_at: datetime | None = None
    preprocessing_error: str | None = None
    summarization: ArticleSummarization | None = None
    embedding_model: str | None = None
    embedding_status: str = "pending"
    event_group_id: str | None = None
    duplicate_detection_status: str = "pending"
    duplicate_checked_at: datetime | None = None
    exact_duplicate_of: str | None = None

    model_config = ConfigDict(extra="forbid")


class NewsQueryParams(BaseModel):
    category: str | None = None
    source: str | None = None
    keyword: str | None = None
    country: str | None = None
    language: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)
    sort_by: str = "published_at"

    model_config = ConfigDict(extra="forbid")
