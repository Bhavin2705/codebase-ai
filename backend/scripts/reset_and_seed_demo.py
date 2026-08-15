import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import AsyncSessionLocal
from sqlalchemy import text
from app.models.repository import Repository
from app.models.indexing_job import IndexingJob
from app.services.indexing_service import IndexingService
import uuid

async def reset_db_and_seed():
    print("1. Wiping entire database...")
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE chats, indexing_jobs, symbols, files, repository_versions, repositories CASCADE;"))
        await session.commit()
    print("Database wiped clean!")

    print("2. Seeding clean demo repository: spring-projects/spring-petclinic...")
    repo_id = uuid.uuid4()
    job_id = uuid.uuid4()
    
    async with AsyncSessionLocal() as session:
        repo = Repository(
            id=repo_id,
            name="spring-projects/spring-petclinic",
            github_url="https://github.com/spring-projects/spring-petclinic",
            language="java",
            status="pending"
        )
        job = IndexingJob(
            id=job_id,
            repository_id=repo_id,
            job_type="full_index",
            status="queued",
            progress=0,
            current_stage="queued"
        )
        session.add(repo)
        session.add(job)
        await session.commit()

    print(f"Created repo {repo_id} and job {job_id}. Running indexing pipeline...")
    service = IndexingService()
    await service.run_pipeline(str(job_id))
    print("Indexing pipeline finished!")

    async with AsyncSessionLocal() as session:
        r = await session.execute(text("SELECT id, name, github_url, status FROM repositories;"))
        repos = r.fetchall()
        print(f"Repositories in DB: {repos}")
        
        f_count = await session.execute(text("SELECT count(*) FROM files;"))
        s_count = await session.execute(text("SELECT count(*) FROM symbols;"))
        print(f"Files indexed: {f_count.scalar()}, Symbols indexed: {s_count.scalar()}")

if __name__ == "__main__":
    asyncio.run(reset_db_and_seed())
