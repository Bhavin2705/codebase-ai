r"""
cleanup_repositories.py
-----------------------
Standalone script: deletes ALL repositories (and their cascaded files,
symbols, chats, indexing_jobs) from the database.

Run manually:
    python scripts/cleanup_repositories.py

Schedule via cron (Linux/macOS) — midnight every day:
    0 0 * * * cd /path/to/backend && python scripts/cleanup_repositories.py

Schedule via Windows Task Scheduler — midnight every day:
    Program : python
    Arguments: D:\Sem7\codebase-knowledge-ai\backend\scripts\cleanup_repositories.py
    Start in : D:\Sem7\codebase-knowledge-ai\backend
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone

# Allow running from repo root or backend/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CLEANUP] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def delete_all_repositories() -> int:
    """Delete every repository row (cascades to files, symbols, chats, jobs).
    Returns the number of repositories deleted."""
    from sqlalchemy import select, delete as sa_delete
    from app.database import AsyncSessionLocal
    from app.models.repository import Repository

    async with AsyncSessionLocal() as db:
        # Count first so we can report a meaningful number
        result = await db.execute(select(Repository))
        repos = result.scalars().all()
        count = len(repos)

        if count == 0:
            logger.info("No repositories found — nothing to delete.")
            return 0

        # CASCADE delete: files, symbols, chats, indexing_jobs all go with it
        await db.execute(sa_delete(Repository))
        await db.commit()
        logger.info("Deleted %d repository records (cascade: files, symbols, chats, jobs).", count)
        return count


async def main():
    started_at = datetime.now(timezone.utc)
    logger.info("=== Repository cleanup started at %s UTC ===", started_at.strftime("%Y-%m-%d %H:%M:%S"))
    try:
        deleted = await delete_all_repositories()
        logger.info("=== Cleanup complete. %d repositories removed. ===", deleted)
    except Exception as err:
        logger.error("Cleanup failed: %s", err, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
