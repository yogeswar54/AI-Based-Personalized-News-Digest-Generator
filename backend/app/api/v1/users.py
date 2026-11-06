from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.schemas.interests import InterestUpdateRequest
from app.schemas.user import ProfileUpdateRequest
from app.services.interest_service import update_user_interests
from app.services.user_service import get_user_profile_response, get_users_collection, serialize_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)) -> dict:
    return get_user_profile_response(current_user)


@router.put("/profile")
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    collection = get_users_collection()
    updated_name = payload.full_name.strip()
    collection.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"full_name": updated_name, "updated_at": datetime.now(timezone.utc)}},
    )
    current_user["full_name"] = updated_name
    current_user["updated_at"] = datetime.now(timezone.utc)
    return {
        "message": "Profile updated successfully",
        "user": serialize_user(current_user),
    }


@router.get("/interests")
async def get_interests(current_user: dict = Depends(get_current_user)) -> dict:
    return {"interests": current_user.get("interests", [])}


@router.put("/interests")
async def update_interests(
    payload: InterestUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    interests = update_user_interests(current_user, payload.interests)
    return {"message": "Interests updated successfully", "interests": interests}
