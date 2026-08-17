import os
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from sqlalchemy import select, delete

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
                await db.commit()

                repo_dir = self.git.clone_repository(repo.github_url)
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
                await db.commit()

                file_pairs = self.git.scan_files(repo_dir)
                repo.language = detect_language(file_pairs)

                files_to_add = []
                symbols_to_add = []

                for rel_path, abs_path in file_pairs:
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as file_handle:
                            code = file_handle.read()

                        ext = os.path.splitext(rel_path)[1].lower()
                        chash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                        file_uuid = uuid.uuid4()

                        file_rec = FileModel(
                            id=file_uuid,
                            repository_id=repo.id,
                            path=rel_path,
                            language=ext or "text",
                            content=code,
                            content_hash=chash,
                        )
                        files_to_add.append(file_rec)

                        parsed_syms = self.parser.parse_file(rel_path, code, ext)
                        for sym_data in parsed_syms:
                            stype = sym_data.get("symbol_type", "function")

                            sym_rec = SymbolModel(
                                id=uuid.uuid4(),
                                file_id=file_uuid,
                                name=sym_data.get("name", "unknown"),
                                symbol_type=stype,
                                signature=sym_data.get("signature"),
                                source_code=sym_data.get("source_code", ""),
                                start_line=sym_data.get("start_line", 1),
                                end_line=sym_data.get("end_line", 1),
                            )
                            symbols_to_add.append(sym_rec)
                    except Exception as file_err:
                        logger.warning("Failed to parse file %s: %s", rel_path, file_err)

                job.current_stage = "embedding"
                job.progress = 60
                await db.commit()

                symbols_with_code = [sym for sym in symbols_to_add if sym.source_code]
                embedding_failures = 0

                for sym in symbols_with_code:
                    try:
                        emb = await self.embedder.generate_embedding(sym.source_code)
                        sym.embedding = emb
                    except Exception as emb_err:
                        embedding_failures += 1
                        logger.error("Failed to generate embedding for symbol %s: %s", sym.name, emb_err)

                if symbols_with_code and embedding_failures == len(symbols_with_code):
                    raise RuntimeError(f"Embedding pipeline failed for all {len(symbols_with_code)} symbols")

                job.current_stage = "storing"
                job.progress = 90
                await db.commit()

                async with db.begin():
                    for file_rec in files_to_add:
                        db.add(file_rec)
                    for symbol_rec in symbols_to_add:
                        db.add(symbol_rec)

                    now_utc = datetime.now(timezone.utc)
                    repo.commit_sha = commit_sha
                    repo.file_count = len(files_to_add)
                    repo.symbol_count = len(symbols_to_add)
                    repo.status = "ready"
                    repo.indexed_at = now_utc

                    job.status = "completed"
                    job.current_stage = "completed"
                    job.progress = 100
                    job.completed_at = now_utc

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


indexing_service = IndexingService()
