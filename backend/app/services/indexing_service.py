import os
import uuid
import logging
import asyncio
import gc
from datetime import datetime, timezone
import numpy as np
from sqlalchemy import select, delete, insert

from app.database import AsyncSessionLocal
from app.models.repository import Repository
from app.models.file import File as FileModel
from app.models.symbol import Symbol as SymbolModel
from app.models.indexing_job import IndexingJob
from app.services.git_service import GitService, detect_language
from app.services.parser_service import CodeParserService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(self):
        self.git = GitService()
        self.parser = CodeParserService()
        self.embedder = EmbeddingService()

    async def run_pipeline(self, job_id_str: str) -> None:
        async with AsyncSessionLocal() as db:
            try:
                job_uuid = uuid.UUID(job_id_str)
            except ValueError:
                return

            stmt = select(IndexingJob).where(IndexingJob.id == job_uuid)
            job = (await db.execute(stmt)).scalars().first()
            if not job:
                return

            stmt_repo = select(Repository).where(Repository.id == job.repository_id)
            repo = (await db.execute(stmt_repo)).scalars().first()
            if not repo:
                job.status = "failed"
                job.error_message = "Repository not found"
                await db.commit()
                return

            repo_dir = None

            try:
                job.status = "running"
                job.current_stage = "cloning"
                job.progress = 10

                repo_dir = self.git.clone_repository(repo.github_url)
                if not repo_dir or not os.path.isdir(repo_dir):
                    raise RuntimeError("Repository clone did not produce a valid directory")

                commit_sha = self.git.get_commit_sha(repo_dir)

                job.current_stage = "parsing"
                job.progress = 30

                now_utc = datetime.now(timezone.utc)

                # If the repository is already indexed at this commit SHA, complete immediately
                if repo.commit_sha == commit_sha and repo.status == "ready":
                    job.status = "completed"
                    job.current_stage = "completed"
                    job.progress = 100
                    job.completed_at = now_utc
                    await db.commit()
                    return

                # Clear previous indexed files & symbols for this repository before writing new ones
                await db.execute(delete(FileModel).where(FileModel.repository_id == repo.id))

                file_pairs = self.git.scan_files(repo_dir)
                if not file_pairs:
                    raise RuntimeError(
                        "Repository contains no supported source files to index"
                    )

                repo.language = detect_language(file_pairs)

                files_data = []
                symbols_data = []

                for rel_path, abs_path in file_pairs:
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as file_handle:
                            code = file_handle.read()

                        ext = os.path.splitext(rel_path)[1].lower()
                        file_uuid = uuid.uuid4()

                        files_data.append({
                            "id": file_uuid,
                            "repository_id": repo.id,
                            "path": rel_path,
                            "language": ext or "text",
                            "content": code,
                        })

                        parsed_syms = self.parser.parse_file(rel_path, code, ext)
                        for sym_data in parsed_syms:
                            stype = sym_data.get("symbol_type", "function")

                            symbols_data.append({
                                "id": uuid.uuid4(),
                                "file_id": file_uuid,
                                "name": sym_data.get("name", "unknown"),
                                "symbol_type": stype,
                                "signature": sym_data.get("signature"),
                                "source_code": sym_data.get("source_code", ""),
                                "start_line": sym_data.get("start_line", 1),
                                "end_line": sym_data.get("end_line", 1),
                                "embedding": None,
                            })
                    except Exception as file_err:
                        logger.warning("Failed to parse file %s: %s", rel_path, file_err)

                if not files_data:
                    raise RuntimeError("No supported files were successfully parsed")

                if not symbols_data:
                    raise RuntimeError("No code symbols/chunks were extracted from the repository")

                job.current_stage = "embedding"
                job.progress = 60

                symbols_with_code_indices = [
                    i for i, sym in enumerate(symbols_data)
                    if sym["source_code"] and sym["source_code"].strip()
                ]

                if symbols_with_code_indices:
                    texts = [symbols_data[i]["source_code"] for i in symbols_with_code_indices]
                    embeddings = await self.embedder.generate_embeddings_batch(texts, batch_size=150)
                    for idx, emb in zip(symbols_with_code_indices, embeddings):
                        symbols_data[idx]["embedding"] = emb

                now_utc = datetime.now(timezone.utc)

                if files_data:
                    for f_batch in [files_data[i:i+500] for i in range(0, len(files_data), 500)]:
                        await db.execute(insert(FileModel), f_batch)

                if symbols_data:
                    raw_conn = await db.connection()
                    dbapi_conn = await raw_conn.get_raw_connection()
                    asyncpg_conn = getattr(
                        dbapi_conn,
                        "driver_connection",
                        getattr(dbapi_conn, "_connection", None),
                    )

                    records = [
                        (
                            s["id"],
                            s["file_id"],
                            s["name"],
                            s["symbol_type"],
                            s["signature"],
                            s["source_code"],
                            s["start_line"],
                            s["end_line"],
                            np.array(s["embedding"], dtype=np.float32) if s["embedding"] is not None else None,
                            now_utc,
                        )
                        for s in symbols_data
                    ]

                    await asyncpg_conn.copy_records_to_table(
                        "symbols",
                        records=records,
                        columns=[
                            "id",
                            "file_id",
                            "name",
                            "symbol_type",
                            "signature",
                            "source_code",
                            "start_line",
                            "end_line",
                            "embedding",
                            "created_at",
                        ],
                    )

                repo.commit_sha = commit_sha
                repo.file_count = len(files_data)
                repo.symbol_count = len(symbols_data)
                repo.status = "ready"
                repo.indexed_at = now_utc

                job.status = "completed"
                job.current_stage = "completed"
                job.progress = 100
                job.completed_at = now_utc
                await db.commit()

            except Exception as err:
                logger.error("Repository indexing pipeline failed for job %s: %s", job_id_str, err, exc_info=True)
                await db.rollback()

                stmt_job_err = select(IndexingJob).where(IndexingJob.id == job_uuid)
                job_err = (await db.execute(stmt_job_err)).scalars().first()
                if job_err:
                    job_err.status = "failed"
                    job_err.error_message = str(err)

                stmt_repo_err = select(Repository).where(Repository.id == job.repository_id)
                repo_err = (await db.execute(stmt_repo_err)).scalars().first()
                if repo_err:
                    if repo_err.commit_sha is not None and repo_err.file_count > 0:
                        repo_err.status = "ready"
                    else:
                        repo_err.status = "error"

                await db.commit()
            finally:
                if repo_dir:
                    self.git.cleanup(repo_dir)
                gc.collect()


indexing_service = IndexingService()
