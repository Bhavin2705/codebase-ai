import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, repositories, chat
from app.config import settings
from app.database import engine, Base
import app.models

logger = logging.getLogger(__name__)

# Define the Indian Standard Time (IST) zone reference offset
IST = timezone(timedelta(hours=5, minutes=30))


def get_cors_origins() -> list[str]:
    """Combines configured environment strings with local framework sandbox origins."""
    default_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://codebase-ai-nine.vercel.app",
    ]
    raw_url = getattr(settings, "FRONTEND_URL", "").strip()
    if raw_url:
        origins = [origin.strip().rstrip("/") for origin in raw_url.split(",")]
        return list(set(origins + default_origins))
    return default_origins


async def _delete_all_repositories() -> int:
    """Delete every repository row (cascades natively to files, symbols, chats, jobs)."""
    from sqlalchemy import select, delete as sa_delete
    from app.database import AsyncSessionLocal
    from app.models.repository import Repository

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Repository))
        count = len(result.scalars().all())
        if count == 0:
            logger.info("[Midnight Cleanup] No repositories to delete.")
            return 0
        await db.execute(sa_delete(Repository))
        await db.commit()
        logger.info("[Midnight Cleanup] Deleted %d repository records (cascade verified).", count)
        return count


async def _midnight_cleanup_loop():
    """Background loop that sleeps precisely until 12:00 AM IST, purges the DB, and repeats daily."""
    while True:
        now_ist = datetime.now(IST)
        
        # Determine the absolute 12:00 AM destination for the next calendar day
        next_midnight_ist = datetime(
            year=now_ist.year,
            month=now_ist.month,
            day=now_ist.day,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=IST
        ) + timedelta(days=1)
        
        seconds_until_midnight = (next_midnight_ist - now_ist).total_seconds()
        
        logger.info(
            "[Midnight Cleanup] Next run in %dh %dm %ds (at 12:00 AM IST).",
            int(seconds_until_midnight // 3600),
            int((seconds_until_midnight % 3600) // 60),
            int(seconds_until_midnight % 60),
        )
        
        await asyncio.sleep(seconds_until_midnight)
        logger.info("[Midnight Cleanup] Running scheduled repository purge...")
        try:
            await _delete_all_repositories()
        except Exception as err:
            logger.error("[Midnight Cleanup] Purge failed: %s", err, exc_info=True)
            
        # 5-second cooldown to safely clear the active calendar second window
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles async app database readiness checks and context background task schedules."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database synchronized successfully.")
    except Exception as err:
        logger.error("Database connection initialization failed: %s", err, exc_info=True)

    # Boot the automated daily sandbox cleanup task loop
    cleanup_task = asyncio.create_task(_midnight_cleanup_loop())
    logger.info("[Midnight Cleanup] Scheduler active for 12:00 AM IST.")

    yield

    # Clean app teardown sequence
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
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active App Routing Interface
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
