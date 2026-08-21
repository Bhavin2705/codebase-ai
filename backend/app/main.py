import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, repositories, chat
from app.config import settings
from app.database import engine, Base
import app.models
from app.services.cleanup import midnight_cleanup_loop

logger = logging.getLogger(__name__)


def get_cors_origins() -> list[str]:
    """Combines configured environment strings with local framework sandbox origins."""
    default_origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "https://codebase-ai-nine.vercel.app",
    ]
    raw_url = getattr(settings, "FRONTEND_URL", "").strip()
    if raw_url:
        origins = [origin.strip().rstrip("/") for origin in raw_url.split(",")]
        return list(set(origins + default_origins))
    return default_origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles async app database readiness checks and context background task schedules."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database synchronized successfully.")
    except Exception as err:
        logger.error("Database connection initialization failed: %s", err, exc_info=True)

    cleanup_task = asyncio.create_task(midnight_cleanup_loop())
    logger.info("[Midnight Cleanup] Scheduler active for 12:00 AM IST.")

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("[Midnight Cleanup] Scheduler gracefully shutdown.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$|https://.*\.vercel\.app",
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
