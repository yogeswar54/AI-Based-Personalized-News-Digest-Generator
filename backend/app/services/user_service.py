from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException, status

from app.database.mongodb import get_database

AVAILABLE_INTERESTS = [
    "Technology",
    "Artificial Intelligence",
    "Business",
    "Finance",
    "Sports",
    "Politics",
    "Entertainment",
    "Science",
    "Health",
    "Education",
    "Startups",
    "World News",
    "Environment",
    "Automobile",
    "Gaming",
]


def get_users_collection():
    database = get_database()
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    users_collection = database["users"]
    users_collection.create_index("email", unique=True)
    return users_collection


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_interests(interests: list[str]) -> list[str]:
    if not isinstance(interests, list) or not interests:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one interest",
        )

    normalized: list[str] = []
    seen: set[str] = set()
    for item in interests:
        if not isinstance(item, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each interest must be a string value",
            )
        cleaned = item.strip()
        if not cleaned:
            continue
        if cleaned not in AVAILABLE_INTERESTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported interest: {cleaned}",
            )
        key = cleaned.lower()
        if key in seen:
            continue
        normalized.append(cleaned)
        seen.add(key)

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one interest",
        )

    return normalized


def serialize_user(user_document: dict) -> dict:
    created_at = user_document.get("created_at")
    updated_at = user_document.get("updated_at")
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    if isinstance(updated_at, datetime):
        updated_at = updated_at.isoformat()

    return {
        "id": str(user_document["_id"]),
        "full_name": user_document.get("full_name"),
        "email": user_document.get("email"),
        "interests": user_document.get("interests", []),
        "is_active": user_document.get("is_active", True),
        "created_at": created_at,
        "updated_at": updated_at,
    }


def get_user_by_email(email: str) -> dict | None:
    users_collection = get_users_collection()
    return users_collection.find_one({"email": normalize_email(email)})


def get_user_by_id(user_id: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    users_collection = get_users_collection()
    return users_collection.find_one({"_id": ObjectId(user_id)})


def get_user_profile_response(user_document: dict) -> dict:
    return {"user": serialize_user(user_document)}


def update_user_timestamp(user_document: dict) -> datetime:
    updated_at = datetime.now(timezone.utc)
    user_document["updated_at"] = updated_at
    return updated_at
