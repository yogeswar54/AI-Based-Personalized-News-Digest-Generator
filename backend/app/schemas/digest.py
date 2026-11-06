from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DigestSettings(BaseModel):
    digest_enabled: bool = False
    digest_frequency: str = "daily"
    digest_time: str = "08:00"
    timezone: str = "UTC"
    articles_per_digest: int = Field(default=10, ge=1, le=50)

    @field_validator("digest_frequency")
    @classmethod
    def validate_frequency(cls, value: str) -> str:
        if value != "daily":
            raise ValueError("Digest frequency must be daily")
        return value

    @field_validator("digest_time")
    @classmethod
    def validate_digest_time(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Digest time must use HH:MM format") from exc
        if len(value) != 5:
            raise ValueError("Digest time must use HH:MM format")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value

    model_config = ConfigDict(extra="forbid")


class DigestGenerationRequest(BaseModel):
    regenerate: bool = False

    model_config = ConfigDict(extra="forbid")
