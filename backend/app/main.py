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
        from sqlalchemy import text
        async with engine.begin() as conn:
            # Perform Phase 2 schema flattening migrations
            await conn.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'repositories') THEN
                        ALTER TABLE repositories DROP CONSTRAINT IF EXISTS fk_repositories_current_version;
                        ALTER TABLE repositories DROP COLUMN IF EXISTS current_version_id;
                        ALTER TABLE repositories ADD COLUMN IF NOT EXISTS commit_sha VARCHAR(40);
                        ALTER TABLE repositories ADD COLUMN IF NOT EXISTS file_count INT NOT NULL DEFAULT 0;
                        ALTER TABLE repositories ADD COLUMN IF NOT EXISTS symbol_count INT NOT NULL DEFAULT 0;
                    END IF;

                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'files') THEN
                        ALTER TABLE files DROP CONSTRAINT IF EXISTS uix_repo_version_file_path;
                        ALTER TABLE files DROP CONSTRAINT IF EXISTS files_repository_version_id_fkey;
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'files' AND column_name = 'repository_version_id') THEN
                            ALTER TABLE files DROP COLUMN repository_version_id;
                        END IF;
                        ALTER TABLE files ADD COLUMN IF NOT EXISTS repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE;
                        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uix_repo_file_path') THEN
                            ALTER TABLE files ADD CONSTRAINT uix_repo_file_path UNIQUE (repository_id, path);
                        END IF;
                    END IF;

                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'indexing_jobs') THEN
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'indexing_jobs' AND column_name = 'repository_version_id') THEN
                            ALTER TABLE indexing_jobs DROP COLUMN repository_version_id;
                        END IF;
                    END IF;

                    DROP TABLE IF EXISTS repository_versions CASCADE;
                END $$;
            """))
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