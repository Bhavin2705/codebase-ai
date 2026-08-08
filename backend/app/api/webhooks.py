import uuid
from fastapi import APIRouter, Request, Header, HTTPException, status, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.repository import Repository
from app.models.indexing_job import IndexingJob
from app.services.webhook_service import verify_signature
from app.services.indexing_service import indexing_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

async def _run_indexing(job_id: str):
    await indexing_service.run_pipeline(job_id)

@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    db: AsyncSession = Depends(get_db)
):
    body_bytes = await request.body()
    if not verify_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    repo_data = payload.get("repository", {})
    html_url = repo_data.get("html_url")
    clone_url = repo_data.get("clone_url")

    stmt = select(Repository).where(
        (Repository.github_url == html_url) | (Repository.github_url == clone_url)
    )
    repo = (await db.execute(stmt)).scalars().first()
    if not repo:
        return {"status": "ignored", "reason": "Repository not tracked"}

    job_uuid = uuid.uuid4()
    job_id = str(job_uuid)

    job = IndexingJob(
        id=job_uuid,
        repository_id=repo.id,
        job_type="webhook_push",
        status="pending",
        current_stage="cloning"
    )
    db.add(job)
    await db.commit()

    background_tasks.add_task(_run_indexing, job_id)
    return {"status": "accepted", "job_id": job_id}
