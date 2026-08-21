import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Indian Standard Time (IST) reference offset
IST = timezone(timedelta(hours=5, minutes=30))


async def delete_all_repositories() -> int:
    """Delete every repository row from database (cascades to files, symbols, chats, jobs)."""
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


async def midnight_cleanup_loop():
    """Background task loop that calculates interval to 12:00 AM IST, purges DB, and repeats daily."""
    while True:
        now_ist = datetime.now(IST)
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
            await delete_all_repositories()
        except Exception as err:
            logger.error("[Midnight Cleanup] Purge failed: %s", err, exc_info=True)

        await asyncio.sleep(5)
