from __future__ import annotations

from datetime import date
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_current_user
from app.schemas.digest import DigestGenerationRequest, DigestSettings
from app.services.digest.digest_service import (
    generate_digest_for_user,
    get_today_digest as get_today_digest_service,
    get_user_digest,
    get_user_digest_history,
    update_user_digest_settings,
    user_digest_settings,
)

router = APIRouter(prefix="/digests", tags=["digests"])


@router.post("/generate")
async def generate_digest(
    payload: DigestGenerationRequest | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return await generate_digest_for_user(current_user, regenerate=bool(payload and payload.regenerate))


@router.get("/today")
async def get_today_digest(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    digest = get_today_digest_service(current_user)
    if digest is None:
        return {"status": "not_generated", "digest": None}
    return {"status": "completed", "digest": digest}


@router.get("/history")
async def get_digest_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        if start_date:
            date.fromisoformat(start_date)
        if end_date:
            date.fromisoformat(end_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dates must use YYYY-MM-DD format") from exc
    return get_user_digest_history(
        current_user["_id"],
        page=page,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/settings")
async def get_digest_settings(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"settings": user_digest_settings(current_user), "interests": current_user.get("interests", [])}


@router.put("/settings")
async def put_digest_settings(
    payload: DigestSettings,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        updated = update_user_digest_settings(current_user["_id"], payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    current_user["digest_settings"] = updated
    return {"message": "Digest settings updated successfully", "settings": updated}


@router.get("/{digest_id}")
async def get_digest(
    digest_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if not ObjectId.is_valid(digest_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digest not found")
    digest = get_user_digest(current_user["_id"], digest_id)
    if digest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digest not found")
    return {"status": digest["status"], "digest": digest}
