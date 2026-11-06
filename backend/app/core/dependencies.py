from fastapi import Depends, HTTPException, Request, status

from app.config import get_settings
from app.core.cors import get_allowed_origins, normalize_origin
from app.core.security import decode_access_token
from app.services.user_service import get_user_by_email

_COOKIE_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_token_from_request(request: Request) -> str:
    token = request.cookies.get(get_settings().cookie_name)
    if token:
        return token

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


async def get_current_user(request: Request) -> dict:
    settings = get_settings()
    cookie_token = request.cookies.get(settings.cookie_name)
    if cookie_token and request.method in _COOKIE_MUTATION_METHODS:
        request_origin = normalize_origin(request.headers.get("Origin"))
        if not request_origin or request_origin not in get_allowed_origins():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request origin is not allowed",
            )

    token = get_token_from_request(request)
    payload = decode_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication payload",
        )

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    return user
