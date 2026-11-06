from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.services.recommendation.recommendation_service import build_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
async def get_recommendations(
    category: str | None = Query(default=None, min_length=1, max_length=80),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["relevance", "published_at", "category"] = Query(default="relevance"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return build_recommendations(
        current_user,
        category=category,
        page=page,
        limit=limit,
        sort_by=sort_by,
    )
