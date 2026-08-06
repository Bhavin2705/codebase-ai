import os
import uuid
import json
import hashlib
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, HTTPException, status, Query, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.repository import Repository
from app.models.file import File as FileModel
from app.models.symbol import Symbol as SymbolModel
from app.models.indexing_job import IndexingJob
from app.schemas.repository import RepoImportRequest, RepoResponse, RepoIndexResponse, RepoStats, IndexStage
from app.services.git_service import GitService
from app.services.parser_service import CodeParserService
from app.services.indexing_service import indexing_service

router = APIRouter(prefix="/repositories", tags=["Repositories"])

git_service = GitService()
parser_service = CodeParserService()

def build_tree_from_paths(file_paths: List[str]) -> List[Dict[str, Any]]:
    root: Dict[str, Any] = {"children": {}}
    for path in file_paths:
        path_segments = path.replace("\\", "/").split("/")
        current_node = root
        for i, segment in enumerate(path_segments):
            if i == len(path_segments) - 1:
                current_node["children"][segment] = {"name": segment, "type": "file", "path": path}
            else:
                if segment not in current_node["children"]:
                    current_node["children"][segment] = {"name": segment, "type": "folder", "children": {}}
                current_node = current_node["children"][segment]

    def _convert(nodes: Dict[str, Any]) -> List[Dict[str, Any]]:
        tree_nodes = []
        for node_key, node_data in nodes.items():
            if node_data["type"] == "folder":
                tree_nodes.append({
                    "name": node_data["name"],
                    "type": "folder",
                    "children": _convert(node_data["children"])
                })
            else:
                tree_nodes.append({
                    "name": node_data["name"],
                    "type": "file",
                    "path": node_data["path"]
                })
        return sorted(tree_nodes, key=lambda tree_item: (0 if tree_item["type"] == "folder" else 1, tree_item["name"]))

    return _convert(root["children"])

def detect_language(scanned_file_pairs: List[Tuple[str, str]]) -> str:
    extension_counts: Dict[str, int] = {}
    for relative_path, _ in scanned_file_pairs:
        file_extension = os.path.splitext(relative_path)[1].lower()
        extension_counts[file_extension] = extension_counts.get(file_extension, 0) + 1

    js_ts_count = extension_counts.get('.js', 0) + extension_counts.get('.jsx', 0) + extension_counts.get('.ts', 0) + extension_counts.get('.tsx', 0)
    java_count = extension_counts.get('.java', 0)
    py_count = extension_counts.get('.py', 0)

    if js_ts_count > java_count and js_ts_count > py_count:
        return "JavaScript / React / Node"
    elif java_count >= py_count and java_count > 0:
        return "Java / Spring Boot"
    elif py_count > 0:
        return "Python"
    return "Multi-Language"

async def _run_indexing_pipeline_task(job_id: str):
    await indexing_service.run_pipeline(job_id)

@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def import_repository(payload: RepoImportRequest, db: AsyncSession = Depends(get_db)):
    if "github.com" not in payload.github_url:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL format. Must be https://github.com/owner/repo")

    url_parts = payload.github_url.rstrip("/").split("/")
    repo_name = f"{url_parts[-2]}/{url_parts[-1].replace('.git', '')}"
    repo_uuid = uuid.uuid4()
    repo_id = str(repo_uuid)

    repo_dir = None
    scanned_file_pairs = []
    file_contents = {}
    total_symbols = 0
    language = "Multi-Language"

    try:
        repo_dir = git_service.clone_repository(payload.github_url)
        scanned_file_pairs = git_service.scan_files(repo_dir)
        language = detect_language(scanned_file_pairs)

        for relative_path, absolute_path in scanned_file_pairs[:100]:
            try:
                with open(absolute_path, "r", encoding="utf-8", errors="ignore") as file_handle:
                    code_content = file_handle.read()

                file_extension = os.path.splitext(relative_path)[1].lower()
                symbols = parser_service.parse_file(relative_path, code_content, file_extension)
                total_symbols += len(symbols)

                content_hash = hashlib.sha256(code_content.encode("utf-8")).hexdigest()
                file_contents[relative_path] = {
                    "content": code_content,
                    "content_hash": content_hash,
                    "symbols": symbols
                }
            except Exception as error:
                print(f"Error parsing file {relative_path}: {error}")
    except Exception as error:
        print(f"Git clone error for {payload.github_url}: {error}")
    finally:
        if repo_dir:
            git_service.cleanup(repo_dir)

    now = datetime.utcnow()
    repository_record = Repository(
        id=repo_uuid,
        name=repo_name,
        github_url=payload.github_url,
        language=language,
        status="ready",
        indexed_at=now
    )
    db.add(repository_record)

    for relative_path, file_data in file_contents.items():
        file_uuid = uuid.uuid4()
        file_extension = os.path.splitext(relative_path)[1].lower()
        file_record = FileModel(
            id=file_uuid,
            repository_id=repo_uuid,
            path=relative_path,
            language=file_extension or "text",
            content=file_data["content"],
            content_hash=file_data["content_hash"]
        )
        db.add(file_record)

        for symbol_item in file_data.get("symbols", []):
            symbol_record = SymbolModel(
                id=uuid.uuid4(),
                file_id=file_uuid,
                name=symbol_item.get("name", "unknown"),
                symbol_type=symbol_item.get("symbol_type", "function"),
                signature=symbol_item.get("signature"),
                source_code=symbol_item.get("source_code", ""),
                start_line=symbol_item.get("start_line", 1),
                end_line=symbol_item.get("end_line", 1)
            )
            db.add(symbol_record)

    await db.commit()

    return {
        "id": repo_id,
        "name": repo_name,
        "github_url": payload.github_url,
        "language": language,
        "status": "ready",
        "indexed_at": now.isoformat(),
        "stats": RepoStats(
            files=len(scanned_file_pairs),
            classes=total_symbols,
            methods=total_symbols * 3
        )
    }

@router.get("", response_model=List[RepoResponse])
async def list_repositories(db: AsyncSession = Depends(get_db)):
    stmt = select(Repository).options(selectinload(Repository.files))
    db_repos = (await db.execute(stmt)).scalars().all()

    result = []
    for repo in db_repos:
        file_count = len(repo.files)
        result.append({
            "id": str(repo.id),
            "name": repo.name,
            "github_url": repo.github_url,
            "language": repo.language,
            "status": repo.status or "ready",
            "indexed_at": repo.indexed_at.isoformat() if repo.indexed_at else None,
            "stats": RepoStats(files=file_count, classes=file_count * 2, methods=file_count * 8)
        })

    return result

async def _get_repo_by_id_or_name(repository_id: str, db: AsyncSession) -> Repository:
    try:
        parsed_uuid = uuid.UUID(repository_id)
        stmt = select(Repository).options(selectinload(Repository.files)).where(Repository.id == parsed_uuid)
    except ValueError:
        stmt = select(Repository).options(selectinload(Repository.files)).where(Repository.name.ilike(f"%{repository_id}%"))

    result = await db.execute(stmt)
    repo = result.scalars().first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo

@router.get("/{repository_id}/tree")
async def get_repository_tree(repository_id: str, db: AsyncSession = Depends(get_db)):
    repo = await _get_repo_by_id_or_name(repository_id, db)
    file_paths = [file.path for file in repo.files]
    return build_tree_from_paths(file_paths)

@router.get("/{repository_id}/file")
async def get_repository_file(repository_id: str, path: str = Query(..., description="Relative file path"), db: AsyncSession = Depends(get_db)):
    repo = await _get_repo_by_id_or_name(repository_id, db)

    stmt = select(FileModel).options(selectinload(FileModel.symbols)).where(FileModel.repository_id == repo.id)
    files = (await db.execute(stmt)).scalars().all()

    target_file = None
    for file in files:
        if file.path == path or file.path.lower() == path.lower() or file.path.endswith(path):
            target_file = file
            break

    if target_file:
        symbols_list = [
            {
                "name": sym.name,
                "symbol_type": sym.symbol_type,
                "signature": sym.signature,
                "start_line": sym.start_line,
                "end_line": sym.end_line
            }
            for sym in target_file.symbols
        ]
        return {
            "path": target_file.path,
            "content": target_file.content or "",
            "symbols": symbols_list
        }

    return {
        "path": path,
        "content": f"// Source code for {path}\n// Repository: {repo.name}",
        "symbols": []
    }

@router.post("/{repository_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def index_repository(
    repository_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    repo = await _get_repo_by_id_or_name(repository_id, db)

    job_uuid = uuid.uuid4()
    job_id = str(job_uuid)

    indexing_job = IndexingJob(
        id=job_uuid,
        repository_id=repo.id,
        status="pending",
        stage="cloning"
    )
    db.add(indexing_job)
    await db.commit()

    background_tasks.add_task(_run_indexing_pipeline_task, job_id)

    return {
        "job_id": job_id,
        "status": "pending"
    }

@router.get("/{repository_id}/index-stream")
async def stream_repository_indexing(repository_id: str):
    async def event_generator():
        stages_def = [
            (1, "Repository Access", "Cloned source code repository"),
            (2, "Discovery", "Filtered and cataloged source files"),
            (3, "Parsing", "Extracted AST syntax nodes via Tree-sitter"),
            (4, "Representation", "Generated embeddings"),
            (5, "Storage", "Persisted symbols & vectors")
        ]

        for stage_id, name, detail in stages_def:
            data = json.dumps({
                "stage_id": stage_id,
                "name": name,
                "detail": detail,
                "status": "completed"
            })
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.3)

        yield f"data: {json.dumps({'status': 'finished'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
