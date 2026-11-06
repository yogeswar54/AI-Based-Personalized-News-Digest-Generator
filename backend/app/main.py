import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.interests import router as categories_router
from app.api.v1.news import router as news_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.digests import router as digests_router
from app.api.v1.routes import router as v1_router
from app.api.v1.users import router as users_router
from app.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.cors import get_allowed_origins
from app.database.mongodb import close_mongodb_connection, connect_to_mongodb
from app.services.news.news_scheduler import shutdown_news_scheduler, start_news_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if not connect_to_mongodb(settings):
        logger.warning("API started in degraded mode because MongoDB is unavailable")
    try:
        start_news_scheduler()
        yield
    finally:
        shutdown_news_scheduler()
        close_mongodb_connection()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


app.include_router(v1_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(users_router, prefix=settings.api_v1_prefix)
app.include_router(categories_router, prefix=settings.api_v1_prefix)
app.include_router(news_router, prefix=settings.api_v1_prefix)
app.include_router(recommendations_router, prefix=settings.api_v1_prefix)
app.include_router(digests_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix=settings.api_v1_prefix)
register_exception_handlers(app)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "status": "success",
        "message": "Welcome to the Personalized News Digest API",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env.casefold() == "development",
    )
