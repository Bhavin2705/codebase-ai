import uuid
import json
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import verify_api_key
from app.models.repository import Repository
from app.models.file import File as FileModel
from app.models.indexing_job import IndexingJob
from app.schemas.repository import RepoImportRequest, RepoResponse, RepoStats
from app.services.indexing_service import indexing_service
from app.services.git_service import GitService

git_service = GitService()

router = APIRouter(prefix="/repositories", tags=["Repositories"])


def build_tree_from_paths(file_paths: List[str]) -> List[Dict[str, Any]]:
    root: Dict[str, Any] = {"children": {}}
    for path in file_paths:
        parts = path.replace("\\", "/").split("/")
        curr = root
        for i, segment in enumerate(parts):
            if i == len(parts) - 1:
                curr["children"][segment] = {"name": segment, "type": "file", "path": path}
            else:
                if segment not in curr["children"]:
                    curr["children"][segment] = {"name": segment, "type": "folder", "children": {}}
                curr = curr["children"][segment]

    def _convert(nodes: Dict[str, Any]) -> List[Dict[str, Any]]:
        tree_nodes = []
        for key, data in nodes.items():
            if data["type"] == "folder":
                tree_nodes.append({
                    "name": data["name"],
                    "type": "folder",
                    "children": _convert(data["children"])
                })
            else:
                tree_nodes.append({
                    "name": data["name"],
                    "type": "file",
                    "path": data["path"]
                })
        return sorted(tree_nodes, key=lambda x: (0 if x["type"] == "folder" else 1, x["name"]))

    return _convert(root["children"])

async def _run_indexing_task(job_id: str):
    await indexing_service.run_pipeline(job_id)


async def _get_repo(repo_id: str, db: AsyncSession) -> Repository:
    try:
        parsed_uuid = uuid.UUID(repo_id)
        stmt = select(Repository).where(Repository.id == parsed_uuid)
    except ValueError:
        stmt = select(Repository).where(Repository.name.ilike(f"%{repo_id}%"))
    repo = (await db.execute(stmt)).scalars().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo

@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
async def import_repository(
    payload: RepoImportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    if "github.com" not in payload.github_url:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL format")

    if not git_service.check_repository_accessible(payload.github_url):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found\nWe couldn't access this GitHub repository. Please check that the URL is correct and that the repository is public or accessible with the configured credentials. No indexing job was created."
        )

    stmt_exist = select(Repository).options(selectinload(Repository.current_version)).where(Repository.github_url == payload.github_url)
    existing_repo = (await db.execute(stmt_exist)).scalars().first()
    if existing_repo:
        file_count = 0
        symbol_count = 0
        commit_sha = None
        if existing_repo.current_version:
            file_count = existing_repo.current_version.file_count
            symbol_count = existing_repo.current_version.symbol_count
            commit_sha = existing_repo.current_version.commit_sha

        return {
            "id": str(existing_repo.id),
            "name": existing_repo.name,
            "github_url": existing_repo.github_url,
            "language": existing_repo.language,
            "status": existing_repo.status or "ready",
            "current_version_id": str(existing_repo.current_version_id) if existing_repo.current_version_id else None,
            "commit_sha": commit_sha,
            "indexed_at": existing_repo.indexed_at,
            "stats": RepoStats(files=file_count, classes=symbol_count, methods=0)
        }

    parts = payload.github_url.rstrip("/").split("/")
    repository_name = f"{parts[-2]}/{parts[-1].replace('.git', '')}"
    repository_id = uuid.uuid4()
    job_id = uuid.uuid4()

    from datetime import timezone
    now_utc = datetime.now(timezone.utc)

    repository = Repository(
        id=repository_id,
        name=repository_name,
        github_url=payload.github_url,
        language="Multi-Language",
        status="pending",
        created_at=now_utc
    )
    db.add(repository)

    indexing_job = IndexingJob(
        id=job_id,
        repository_id=repository_id,
        job_type="full_index",
        status="pending",
        current_stage="cloning"
    )
    db.add(indexing_job)
    await db.commit()

    background_tasks.add_task(_run_indexing_task, str(job_id))

    return {
        "id": str(repository_id),
        "name": repository_name,
        "github_url": payload.github_url,
        "language": "Multi-Language",
        "status": "pending",
        "current_version_id": None,
        "commit_sha": None,
        "indexed_at": None,
        "stats": RepoStats(files=0, classes=0, methods=0)
    }


@router.get("", response_model=List[RepoResponse])
async def list_repositories(db: AsyncSession = Depends(get_db)):
    stmt = select(Repository).options(selectinload(Repository.current_version))
    repos = (await db.execute(stmt)).scalars().all()

    result = []
    for repo in repos:
        file_cnt = 0
        sym_cnt = 0
        commit_sha = None
        if repo.current_version:
            file_cnt = repo.current_version.file_count
            sym_cnt = repo.current_version.symbol_count
            commit_sha = repo.current_version.commit_sha

        result.append({
            "id": str(repo.id),
            "name": repo.name,
            "github_url": repo.github_url,
            "language": repo.language,
            "status": repo.status or "ready",
            "current_version_id": str(repo.current_version_id) if repo.current_version_id else None,
            "commit_sha": commit_sha,
            "indexed_at": repo.indexed_at,
            "stats": RepoStats(files=file_cnt, classes=sym_cnt, methods=0)
        })

    return result

@router.get("/{repository_id}/tree")
async def get_repository_tree(repository_id: str, db: AsyncSession = Depends(get_db)):
    repo = await _get_repo(repository_id, db)
    paths = []
    if repo.current_version_id:
        stmt = select(FileModel.path).where(FileModel.repository_version_id == repo.current_version_id)
        paths = (await db.execute(stmt)).scalars().all()

    return build_tree_from_paths(list(paths))

@router.get("/{repository_id}/file")
async def get_repository_file(repository_id: str, path: str = Query(...), db: AsyncSession = Depends(get_db)):
    repo = await _get_repo(repository_id, db)
    if not repo.current_version_id:
        raise HTTPException(status_code=404, detail="File not found")

    stmt = (
        select(FileModel)
        .options(selectinload(FileModel.symbols))
        .where(
            FileModel.repository_version_id == repo.current_version_id,
            FileModel.path == path
        )
    )
    target = (await db.execute(stmt)).scalars().first()

    if not target:
        # Fallback to case-insensitive or ending match if exact path not matched
        stmt_fallback = (
            select(FileModel)
            .options(selectinload(FileModel.symbols))
            .where(FileModel.repository_version_id == repo.current_version_id)
        )
        all_files = (await db.execute(stmt_fallback)).scalars().all()
        for f in all_files:
            if f.path.lower() == path.lower() or f.path.endswith(path):
                target = f
                break

    if not target:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    symbols_list = [
        {
            "name": sym.name,
            "symbol_type": sym.symbol_type,
            "signature": sym.signature,
            "start_line": sym.start_line,
            "end_line": sym.end_line
        }
        for sym in target.symbols
    ]
    return {
        "path": target.path,
        "content": target.content or "",
        "symbols": symbols_list
    }

@router.post("/{repository_id}/index", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_api_key)])
async def index_repository(
    repository_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    repo = await _get_repo(repository_id, db)
    job_uuid = uuid.uuid4()
    job_id = str(job_uuid)

    job = IndexingJob(
        id=job_uuid,
        repository_id=repo.id,
        status="pending",
        current_stage="cloning"
    )
    db.add(job)
    await db.commit()

    background_tasks.add_task(_run_indexing_task, job_id)
    return {"job_id": job_id, "status": "pending"}

@router.post("/{repository_id}/sync", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_api_key)])
async def sync_repository(
    repository_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    repo = await _get_repo(repository_id, db)
    job_uuid = uuid.uuid4()
    job_id = str(job_uuid)

    job = IndexingJob(
        id=job_uuid,
        repository_id=repo.id,
        job_type="sync",
        status="pending",
        current_stage="cloning"
    )
    db.add(job)
    await db.commit()

    background_tasks.add_task(_run_indexing_task, job_id)
    return {"job_id": job_id, "status": "pending", "message": "Synchronization started"}

@router.get("/{repository_id}/indexing-jobs/{job_id}")
async def get_indexing_job_status(repository_id: str, job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    stmt = select(IndexingJob).where(IndexingJob.id == job_uuid)
    job = (await db.execute(stmt)).scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Indexing job not found")

    return {
        "job_id": str(job.id),
        "status": job.status,
        "stage": job.current_stage,
        "progress": job.progress,
        "error_message": job.error_message,
        "started_at": job.started_at,
        "completed_at": job.completed_at
    }

@router.get("/{repository_id}/index-stream")
async def stream_repository_indexing(repository_id: str, db: AsyncSession = Depends(get_db)):
    repository = await _get_repo(repository_id, db)
    repo_uuid = repository.id

    async def event_generator():
        import asyncio
        from app.database import AsyncSessionLocal

        stage_details = {
            "cloning": (1, "Repository Access", "Cloning source code repository"),
            "parsing": (2, "Discovery & Parsing", "Cataloging files and extracting AST nodes"),
            "embedding": (3, "Representation", "Generating vector embeddings"),
            "storing": (4, "Storage", "Persisting symbols & vector embeddings"),
            "completed": (4, "Storage", "Persisted symbols & vector embeddings")
        }

        last_stage_id = 0
        max_polls = 180  # Up to 90 seconds

        for _ in range(max_polls):
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(IndexingJob)
                    .where(IndexingJob.repository_id == repo_uuid)
                    .order_by(IndexingJob.created_at.desc())
                )
                job = (await session.execute(stmt)).scalars().first()

            if not job:
                event_payload = {
                    "stage_id": 1,
                    "name": "Repository Access",
                    "detail": "Initializing indexing pipeline",
                    "status": "active"
                }
                yield f"data: {json.dumps(event_payload)}\n\n"
                await asyncio.sleep(0.5)
                continue

            if job.status == "failed":
                yield f"data: {json.dumps({'status': 'failed', 'error': job.error_message or 'Indexing failed'})}\n\n"
                return

            stage_info = stage_details.get(
                job.current_stage or "cloning",
                (1, "Repository Access", "Cloning source code repository")
            )
            stage_id, stage_name, stage_detail = stage_info

            # Emit stage update
            event_payload = {
                "stage_id": stage_id,
                "name": stage_name,
                "detail": stage_detail,
                "status": "completed" if (job.status == "completed" or stage_id < last_stage_id) else "active"
            }
            yield f"data: {json.dumps(event_payload)}\n\n"
            last_stage_id = max(last_stage_id, stage_id)

            if job.status == "completed":
                # Ensure all 4 stages marked complete
                for s_id in range(1, 5):
                    s_name = ["Repository Access", "Discovery & Parsing", "Representation", "Storage"][s_id - 1]
                    s_det = ["Cloned source repository", "Cataloged files & AST nodes", "Generated vector embeddings", "Persisted symbols & vectors"][s_id - 1]
                    yield f"data: {json.dumps({'stage_id': s_id, 'name': s_name, 'detail': s_det, 'status': 'completed'})}\n\n"
                yield f"data: {json.dumps({'status': 'finished'})}\n\n"
                return

            await asyncio.sleep(0.5)

        # Timeout fallback
        yield f"data: {json.dumps({'status': 'finished'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
