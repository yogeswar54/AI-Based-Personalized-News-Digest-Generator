from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.core.dependencies import get_current_user
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import authenticate_user as authenticate_user_service
from app.services.auth_service import register_user as register_user_service
from app.services.user_service import serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])


def set_auth_cookie(response: Response, token: str) -> None:
    from app.config import get_settings

    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(payload: RegisterRequest) -> dict:
    user = register_user_service(payload)
    return {"message": "User registered successfully", "user": user}


@router.post("/login")
async def login_user(payload: LoginRequest, response: Response) -> dict:
    user, token = authenticate_user_service(payload)
    set_auth_cookie(response, token)
    return {"message": "Login successful", "user": user}


@router.post("/logout")
async def logout_user(response: Response) -> dict:
    from app.config import get_settings

    settings = get_settings()
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    return {"message": "Logout successful"}


@router.get("/me")
async def get_current_user_profile(current_user: dict = Depends(get_current_user)) -> dict:
    return {"user": serialize_user(current_user)}
