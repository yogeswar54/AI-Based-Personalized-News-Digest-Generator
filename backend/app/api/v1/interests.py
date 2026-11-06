from fastapi import APIRouter

from app.services.interest_service import get_available_categories

router = APIRouter(tags=["interests"])


@router.get("/interests/categories")
async def get_interest_categories() -> dict:
    return {"categories": get_available_categories()}
