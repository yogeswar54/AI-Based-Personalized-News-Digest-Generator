from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.services.user_service import AVAILABLE_INTERESTS, get_users_collection, normalize_interests


def get_available_categories() -> list[str]:
    return AVAILABLE_INTERESTS


def get_user_interests(user_document: dict) -> list[str]:
    return user_document.get("interests", [])


def update_user_interests(user_document: dict, interests: list[str]) -> list[str]:
    normalized = normalize_interests(interests)
    users_collection = get_users_collection()
    users_collection.update_one(
        {"_id": user_document["_id"]},
        {"$set": {"interests": normalized, "updated_at": datetime.now(timezone.utc)}},
    )
    return normalized
