from urllib.parse import urlsplit

from app.config import get_settings

_DEVELOPMENT_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def normalize_origin(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def get_allowed_origins() -> list[str]:
    settings = get_settings()
    origins = {normalize_origin(settings.frontend_url)}
    if settings.app_env.casefold() in {"development", "test"}:
        origins.update(_DEVELOPMENT_ORIGINS)
    return sorted(origin for origin in origins if origin)
