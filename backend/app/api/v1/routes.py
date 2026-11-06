from typing import Any

from fastapi import APIRouter, Response

from app.database.mongodb import is_mongodb_available

router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, Any]:
    mongodb_status = "connected" if is_mongodb_available() else "unavailable"
    return {
        "status": "success" if mongodb_status == "connected" else "degraded",
        "message": "Personalized News Digest API is running",
        "dependencies": {"mongodb": mongodb_status},
    }


@router.get("/health/ready", tags=["health"])
def readiness_check(response: Response) -> dict[str, Any]:
    mongodb_status = "connected" if is_mongodb_available() else "unavailable"
    if mongodb_status != "connected":
        response.status_code = 503
    return {
        "status": "success" if mongodb_status == "connected" else "not_ready",
        "dependencies": {"mongodb": mongodb_status},
    }
