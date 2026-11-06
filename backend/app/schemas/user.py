from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)

    model_config = ConfigDict(extra="forbid")


class UserPublic(BaseModel):
    id: str
    full_name: str
    email: str
    interests: list[str] = []
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
