from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.user_service import (
    get_user_by_email,
    get_users_collection,
    normalize_email,
    serialize_user,
)


def register_user(payload: RegisterRequest) -> dict:
    users_collection = get_users_collection()
    normalized_email = normalize_email(payload.email)
    if users_collection.find_one({"email": normalized_email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user_document = {
        "full_name": payload.full_name.strip(),
        "email": normalized_email,
        "password_hash": hash_password(payload.password),
        "interests": [],
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = users_collection.insert_one(user_document)
    created_user = users_collection.find_one({"_id": result.inserted_id})
    if created_user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User could not be created",
        )
    return serialize_user(created_user)


def authenticate_user(payload: LoginRequest) -> tuple[dict, str]:
    user_document = get_user_by_email(payload.email)
    if not user_document:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(payload.password, user_document["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user_document["email"])
    return serialize_user(user_document), token
