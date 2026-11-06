from pydantic import BaseModel, ConfigDict, Field


class InterestUpdateRequest(BaseModel):
    interests: list[str] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")
