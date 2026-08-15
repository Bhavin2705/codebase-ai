import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, repositories, chat
from app.config import settings
from app.database import engine, Base

import app.models

logger = logging.getLogger(__name__)


def get_cors_origins() -> list[str]:
    raw_url = getattr(settings, "FRONTEND_URL", "").strip()
    configured_origins = []
    if raw_url:
        for origin in raw_url.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned and cleaned not in configured_origins:
                configured_origins.append(cleaned)

    default_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://codebase-ai-nine.vercel.app",
    ]
    for origin in default_origins:
        if origin not in configured_origins:
            configured_origins.append(origin)
    return configured_origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as err:
        logger.error("Database table initialization failed: %s", err, exc_info=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(repositories.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
    }