import json
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    mongodb_uri: str = Field(default="mongodb://localhost:27017", min_length=1)
    app_env: str = Field(default="development", validation_alias=AliasChoices("app_env", "APP_ENV"))
    database_name: str = Field(default="personalized_news_digest", min_length=1)
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535, validation_alias=AliasChoices("api_port", "API_PORT", "PORT"))
    frontend_url: str = "http://localhost:5173"
    secret_key: str = "development-secret-key-change-in-production"
    ai_api_key: str = Field(default="", validation_alias=AliasChoices("ai_api_key", "AI_API_KEY"))
    gemini_api_key: str = Field(default="", validation_alias=AliasChoices("gemini_api_key", "GEMINI_API_KEY", "ai_api_key", "AI_API_KEY"))
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias=AliasChoices("gemini_model", "GEMINI_MODEL"))
    news_api_key: str = ""
    news_api_base_url: str = "https://newsapi.org/v2"
    news_summarization_enabled: bool = Field(default=False, validation_alias=AliasChoices("news_summarization_enabled", "NEWS_SUMMARIZATION_ENABLED"))
    news_summarization_interval_minutes: int = Field(default=60, ge=1, validation_alias=AliasChoices("news_summarization_interval_minutes", "NEWS_SUMMARIZATION_INTERVAL_MINUTES"))
    news_summarization_batch_size: int = Field(default=10, ge=1, le=100, validation_alias=AliasChoices("news_summarization_batch_size", "NEWS_SUMMARIZATION_BATCH_SIZE"))
    news_summarization_max_input_chars: int = Field(default=30000, ge=1000, le=100000, validation_alias=AliasChoices("news_summarization_max_input_chars", "NEWS_SUMMARIZATION_MAX_INPUT_CHARS"))
    embedding_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", min_length=1, validation_alias=AliasChoices("embedding_model_name", "EMBEDDING_MODEL_NAME"))
    news_duplicate_threshold: float = Field(default=0.85, ge=-1, le=1, validation_alias=AliasChoices("news_duplicate_threshold", "NEWS_DUPLICATE_THRESHOLD"))
    news_similarity_threshold: float = Field(default=0.75, ge=-1, le=1, validation_alias=AliasChoices("news_similarity_threshold", "NEWS_SIMILARITY_THRESHOLD"))
    news_similarity_lookback_days: int = Field(default=7, ge=1, le=90, validation_alias=AliasChoices("news_similarity_lookback_days", "NEWS_SIMILARITY_LOOKBACK_DAYS"))
    news_similarity_candidate_limit: int = Field(default=100, ge=1, le=1000, validation_alias=AliasChoices("news_similarity_candidate_limit", "NEWS_SIMILARITY_CANDIDATE_LIMIT"))
    news_deduplication_enabled: bool = Field(default=False, validation_alias=AliasChoices("news_deduplication_enabled", "NEWS_DEDUPLICATION_ENABLED"))
    news_deduplication_interval_minutes: int = Field(default=15, ge=1, validation_alias=AliasChoices("news_deduplication_interval_minutes", "NEWS_DEDUPLICATION_INTERVAL_MINUTES"))
    news_deduplication_batch_size: int = Field(default=25, ge=1, le=200, validation_alias=AliasChoices("news_deduplication_batch_size", "NEWS_DEDUPLICATION_BATCH_SIZE"))
    news_embedding_batch_size: int = Field(default=16, ge=1, le=128, validation_alias=AliasChoices("news_embedding_batch_size", "NEWS_EMBEDDING_BATCH_SIZE"))
    recommendation_category_weight: float = Field(default=0.60, ge=0, le=1, validation_alias=AliasChoices("recommendation_category_weight", "RECOMMENDATION_CATEGORY_WEIGHT"))
    recommendation_keyword_weight: float = Field(default=0.15, ge=0, le=1, validation_alias=AliasChoices("recommendation_keyword_weight", "RECOMMENDATION_KEYWORD_WEIGHT"))
    recommendation_recency_weight: float = Field(default=0.15, ge=0, le=1, validation_alias=AliasChoices("recommendation_recency_weight", "RECOMMENDATION_RECENCY_WEIGHT"))
    recommendation_content_weight: float = Field(default=0.10, ge=0, le=1, validation_alias=AliasChoices("recommendation_content_weight", "RECOMMENDATION_CONTENT_WEIGHT"))
    recommendation_lookback_days: int = Field(default=30, ge=1, le=365, validation_alias=AliasChoices("recommendation_lookback_days", "RECOMMENDATION_LOOKBACK_DAYS"))
    recommendation_candidate_limit: int = Field(default=500, ge=1, le=5000, validation_alias=AliasChoices("recommendation_candidate_limit", "RECOMMENDATION_CANDIDATE_LIMIT"))
    recommendation_diversity_tolerance: float = Field(default=0.12, ge=0, le=0.5, validation_alias=AliasChoices("recommendation_diversity_tolerance", "RECOMMENDATION_DIVERSITY_TOLERANCE"))
    digest_repeat_exclusion_days: int = Field(default=2, ge=0, le=30, validation_alias=AliasChoices("digest_repeat_exclusion_days", "DIGEST_REPEAT_EXCLUSION_DAYS"))
    digest_scheduler_interval_minutes: int = Field(default=5, ge=1, le=60, validation_alias=AliasChoices("digest_scheduler_interval_minutes", "DIGEST_SCHEDULER_INTERVAL_MINUTES"))
    digest_scheduler_batch_size: int = Field(default=100, ge=1, le=1000, validation_alias=AliasChoices("digest_scheduler_batch_size", "DIGEST_SCHEDULER_BATCH_SIZE"))
    digest_generation_lease_minutes: int = Field(default=15, ge=1, le=120, validation_alias=AliasChoices("digest_generation_lease_minutes", "DIGEST_GENERATION_LEASE_MINUTES"))
    digest_scheduler_enabled: bool = Field(default=False, validation_alias=AliasChoices("digest_scheduler_enabled", "DIGEST_SCHEDULER_ENABLED"))
    news_api_default_language: str = "en"
    news_api_default_country: str = "us"
    news_collection_interval_minutes: int = Field(default=30, ge=1)
    news_preprocessing_interval_minutes: int = Field(default=10, ge=1)
    news_collection_page_size: int = Field(default=20, ge=1, le=100)
    news_preprocessing_batch_size: int = Field(default=25, ge=1, le=200)
    rss_feed_urls: str | list[str] = Field(
        default_factory=lambda: [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://www.reddit.com/r/worldnews/.rss",
        ]
    )

    @field_validator("rss_feed_urls", mode="before")
    @classmethod
    def parse_rss_feed_urls(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    admin_secret_key: str = "development-admin-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices("jwt_expire_minutes", "JWT_ACCESS_TOKEN_EXPIRE_MINUTES"),
    )
    cookie_name: str = "news_digest_session"
    cookie_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("cookie_secure", "COOKIE_SECURE"),
    )
    cookie_samesite: str = Field(default="lax", validation_alias=AliasChoices("cookie_samesite", "COOKIE_SAMESITE"))
    app_name: str = "Personalized News Digest API"
    api_v1_prefix: str = "/api/v1"

    @model_validator(mode="after")
    def validate_deployment_security(self) -> "Settings":
        self.cookie_samesite = self.cookie_samesite.casefold()
        if self.cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be lax, strict, or none")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true when COOKIE_SAMESITE is none")
        if self.app_env.casefold() not in {"development", "test", "staging", "production"}:
            raise ValueError("APP_ENV must be development, test, staging, or production")
        if self.app_env.casefold() in {"staging", "production"}:
            if (
                len(self.secret_key.strip()) < 32
                or self.secret_key.strip() == "development-secret-key-change-in-production"
            ):
                raise ValueError("SECRET_KEY must be a unique value with at least 32 characters outside development")
            if (
                len(self.admin_secret_key.strip()) < 32
                or self.admin_secret_key.strip() == "development-admin-key"
            ):
                raise ValueError("ADMIN_SECRET_KEY must be a unique value with at least 32 characters outside development")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true outside development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
