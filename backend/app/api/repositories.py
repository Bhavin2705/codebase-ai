import uuid
from datetime import datetime
from typing import List, Dict, Any

from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Query,
    Depends,
    BackgroundTasks,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import verify_api_key
from app.limiter import rate_limit
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
                curr["children"][segment] = {
                    "name": segment,
                    "type": "file",
                    "path": path,
                }
            else:
                if segment not in curr["children"]:
                    curr["children"][segment] = {
                        "name": segment,
                        "type": "folder",
                        "children": {},
                    }

                curr = curr["children"][segment]

    def _convert(nodes: Dict[str, Any]) -> List[Dict[str, Any]]:
        tree_nodes = []

        for key, data in nodes.items():
            if data["type"] == "folder":
                tree_nodes.append({
                    "name": data["name"],
                    "type": "folder",
                    "children": _convert(data["children"]),
                })
            else:
                tree_nodes.append({
                    "name": data["name"],
                    "type": "file",
                    "path": data["path"],
                })

        return tree_nodes

    return _convert(root["children"])


async def _run_indexing_task(job_id_str: str):
    await indexing_service.run_pipeline(job_id_str)


async def _get_repo(repository_id: str, db: AsyncSession) -> Repository:
    try:
        repo_uuid = uuid.UUID(repository_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository_id format",
        )

    stmt = select(Repository).where(Repository.id == repo_uuid)
    repo = (await db.execute(stmt)).scalars().first()

    if not repo:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return repo


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RepoResponse,
    dependencies=[Depends(verify_api_key), Depends(rate_limit(limit_count=5, window_seconds=60, tag="repo_import"))],
)
async def import_repository(
    payload: RepoImportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    clean_url = payload.github_url.strip()

    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository URL",
        )

    # Fast preflight check
    is_accessible = git_service.check_repository_accessible(clean_url)

    if not is_accessible:
        raise HTTPException(
            status_code=404,
            detail="Repository not found or is private on GitHub. No indexing job was created.",
        )

    stmt_exist = select(Repository).where(
        Repository.github_url == clean_url
    )
    existing_repo = (await db.execute(stmt_exist)).scalars().first()

    if existing_repo:
        return {
            "id": str(existing_repo.id),
            "name": existing_repo.name,
            "github_url": existing_repo.github_url,
            "language": existing_repo.language,
            "status": existing_repo.status or "ready",
            "commit_sha": existing_repo.commit_sha,
            "indexed_at": existing_repo.indexed_at,
            "stats": RepoStats(
                files=existing_repo.file_count,
                symbols=existing_repo.symbol_count,
            ),
        }

    parts = clean_url.rstrip("/").split("/")
    repository_name = (
        f"{parts[-2]}/{parts[-1].replace('.git', '')}"
    )

    repository_id = uuid.uuid4()
    job_id = uuid.uuid4()

    from datetime import timezone

    now_utc = datetime.now(timezone.utc)

    repository = Repository(
        id=repository_id,
        name=repository_name,
        github_url=clean_url,
        language="Multi-Language",
        status="pending",
        created_at=now_utc,
    )

    db.add(repository)

    indexing_job = IndexingJob(
        id=job_id,
        repository_id=repository_id,
        status="pending",
        current_stage="cloning",
    )

    db.add(indexing_job)
    await db.commit()

    background_tasks.add_task(
        _run_indexing_task,
        str(job_id),
    )

    return {
        "id": str(repository_id),
        "name": repository_name,
        "github_url": payload.github_url,
        "language": "Multi-Language",
        "status": "pending",
        "commit_sha": None,
        "indexed_at": None,
        "stats": RepoStats(files=0, symbols=0),
    }


@router.get(
    "",
    response_model=List[RepoResponse],
)
async def list_repositories(
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Repository)
    repos = (await db.execute(stmt)).scalars().all()

    result = []

    for repo in repos:
        result.append({
            "id": str(repo.id),
            "name": repo.name,
            "github_url": repo.github_url,
            "language": repo.language,
            "status": repo.status or "ready",
            "commit_sha": repo.commit_sha,
            "indexed_at": repo.indexed_at,
            "stats": RepoStats(
                files=repo.file_count,
                symbols=repo.symbol_count,
            ),
        })

    return result


@router.get("/{repository_id}/tree")
async def get_repository_tree(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo(repository_id, db)

    stmt = select(FileModel.path).where(
        FileModel.repository_id == repo.id
    )

    paths = (await db.execute(stmt)).scalars().all()

    return build_tree_from_paths(list(paths))


@router.get("/{repository_id}/file")
async def get_repository_file(
    repository_id: str,
    path: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo(repository_id, db)

    import urllib.parse
    cleaned_path = urllib.parse.unquote(path).replace("\\", "/").strip()
    while cleaned_path.startswith("./"):
        cleaned_path = cleaned_path[2:]
    cleaned_path = cleaned_path.lstrip("/")

    if ".." in cleaned_path or not cleaned_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid path format",
        )

    # 1. Exact path match
    stmt = select(FileModel).where(
        FileModel.repository_id == repo.id,
        FileModel.path == cleaned_path,
    )
    target = (await db.execute(stmt)).scalars().first()

    # 2. Case-insensitive match fallback
    if not target:
        stmt_case = select(FileModel).where(
            FileModel.repository_id == repo.id,
            FileModel.path.ilike(cleaned_path),
        )
        target = (await db.execute(stmt_case)).scalars().first()

    # 3. Suffix match fallback (in case path included repository root or prefix folder)
    if not target:
        stmt_suffix = select(FileModel).where(
            FileModel.repository_id == repo.id,
            FileModel.path.ilike(f"%/{cleaned_path}"),
        )
        target = (await db.execute(stmt_suffix)).scalars().first()

    # 4. Filename match fallback if path contained subdirectories
    if not target and "/" in cleaned_path:
        filename_only = cleaned_path.split("/")[-1]
        stmt_name = select(FileModel).where(
            FileModel.repository_id == repo.id,
            FileModel.path.ilike(f"%{filename_only}"),
        )
        target = (await db.execute(stmt_name)).scalars().first()

    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {cleaned_path}",
        )

    from app.models.symbol import Symbol as SymbolModel
    stmt_syms = (
        select(
            SymbolModel.name,
            SymbolModel.symbol_type,
            SymbolModel.signature,
            SymbolModel.start_line,
            SymbolModel.end_line,
        )
        .where(SymbolModel.file_id == target.id)
        .order_by(SymbolModel.start_line.asc())
    )
    sym_rows = (await db.execute(stmt_syms)).all()

    symbols_list = [
        {
            "name": row[0],
            "symbol_type": row[1],
            "signature": row[2],
            "start_line": row[3],
            "end_line": row[4],
        }
        for row in sym_rows
    ]

    return {
        "path": target.path,
        "content": target.content or "",
        "symbols": symbols_list,
    }


@router.post(
    "/{repository_id}/index",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_key), Depends(rate_limit(limit_count=5, window_seconds=60, tag="repo_index"))],
)
async def index_repository(
    repository_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    repo = await _get_repo(repository_id, db)

    job_uuid = uuid.uuid4()
    job_id = str(job_uuid)

    job = IndexingJob(
        id=job_uuid,
        repository_id=repo.id,
        status="pending",
        current_stage="cloning",
    )

    db.add(job)
    await db.commit()

    background_tasks.add_task(
        _run_indexing_task,
        job_id,
    )

    return {
        "job_id": job_id,
        "status": "pending",
    }




@router.get("/{repository_id}/indexing-jobs/{job_id}")
async def get_indexing_job_status(
    repository_id: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid job_id format",
        )

    stmt = select(IndexingJob).where(
        IndexingJob.id == job_uuid
    )

    job = (await db.execute(stmt)).scalars().first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Indexing job not found",
        )

    return {
        "job_id": str(job.id),
        "status": job.status,
        "stage": job.current_stage,
        "progress": job.progress,
        "error_message": job.error_message,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }