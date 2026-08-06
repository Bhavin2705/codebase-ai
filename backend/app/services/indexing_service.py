import os
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.repository import Repository
from app.models.repository_version import RepositoryVersion
from app.models.file import File as FileModel
from app.models.symbol import Symbol as SymbolModel
from app.models.indexing_job import IndexingJob
from app.services.git_service import GitService
from app.services.parser_service import CodeParserService
from app.services.embedding_service import EmbeddingService


class IndexingService:
    def __init__(self):
        self.git_service = GitService()
        self.parser_service = CodeParserService()
        self.embedding_service = EmbeddingService()

    def _detect_language(self, scanned_file_pairs: List[Tuple[str, str]]) -> str:
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
            repo_version = None

            try:
                # 1. Stage: cloning
                job.status = "running"
                job.stage = "cloning"
                await db.commit()

                repo_dir = self.git_service.clone_repository(repo.github_url)

                commit_sha = "head"
                try:
                    if hasattr(self.git_service, "get_commit_sha"):
                        commit_sha = self.git_service.get_commit_sha(repo_dir)
                    else:
                        commit_sha = hashlib.sha256(f"{repo.id}-{datetime.utcnow()}".encode("utf-8")).hexdigest()[:8]
                except Exception:
                    commit_sha = hashlib.sha256(f"{repo.id}-{datetime.utcnow()}".encode("utf-8")).hexdigest()[:8]

                # 2. Stage: parsing
                job.stage = "parsing"
                repo_version = RepositoryVersion(
                    id=uuid.uuid4(),
                    repository_id=repo.id,
                    commit_sha=commit_sha,
                    status="pending"
                )
                db.add(repo_version)
                await db.commit()

                scanned_file_pairs = self.git_service.scan_files(repo_dir)
                language = self._detect_language(scanned_file_pairs)
                repo.language = language

                file_records_to_add = []
                symbol_records_to_add = []

                for relative_path, absolute_path in scanned_file_pairs:
                    try:
                        with open(absolute_path, "r", encoding="utf-8", errors="ignore") as file_handle:
                            code_content = file_handle.read()

                        file_extension = os.path.splitext(relative_path)[1].lower()
                        parsed_symbols = self.parser_service.parse_file(relative_path, code_content, file_extension)

                        content_hash = hashlib.sha256(code_content.encode("utf-8")).hexdigest()
                        file_uuid = uuid.uuid4()

                        file_record = FileModel(
                            id=file_uuid,
                            repository_id=repo.id,
                            path=relative_path,
                            language=file_extension or "text",
                            content=code_content,
                            content_hash=content_hash
                        )
                        file_records_to_add.append(file_record)

                        for sym_data in parsed_symbols:
                            sym_record = SymbolModel(
                                id=uuid.uuid4(),
                                file_id=file_uuid,
                                name=sym_data.get("name", "unknown"),
                                symbol_type=sym_data.get("symbol_type", "function"),
                                signature=sym_data.get("signature"),
                                source_code=sym_data.get("source_code", ""),
                                start_line=sym_data.get("start_line", 1),
                                end_line=sym_data.get("end_line", 1)
                            )
                            symbol_records_to_add.append(sym_record)
                    except Exception as parse_err:
                        print(f"Error parsing file {relative_path}: {parse_err}")

                # 3. Stage: embedding
                job.stage = "embedding"
                await db.commit()

                for sym in symbol_records_to_add[:20]:
                    if sym.source_code:
                        try:
                            emb = await self.embedding_service.generate_embedding(sym.source_code)
                            sym.embedding = emb
                        except Exception as emb_err:
                            print(f"Embedding error for symbol {sym.name}: {emb_err}")

                # 4. Stage: storage (Strict Database Transaction)
                job.stage = "storage"
                await db.commit()

                async with db.begin():
                    # Clean up existing files and symbols before adding newly indexed ones
                    existing_files_stmt = select(FileModel).where(FileModel.repository_id == repo.id)
                    existing_files = (await db.execute(existing_files_stmt)).scalars().all()
                    for ef in existing_files:
                        await db.delete(ef)

                    for f in file_records_to_add:
                        db.add(f)

                    for s in symbol_records_to_add:
                        db.add(s)

                    repo_version.status = "active"
                    repo.status = "ready"
                    repo.indexed_at = datetime.utcnow()

                    job.status = "completed"
                    job.stage = "completed"
                    job.completed_at = datetime.utcnow()

            except Exception as pipeline_err:
                await db.rollback()
                job.status = "failed"
                job.error_message = str(pipeline_err)
                if repo_version:
                    repo_version.status = "failed"
                repo.status = "error"
                await db.commit()
            finally:
                if repo_dir:
                    self.git_service.cleanup(repo_dir)


indexing_service = IndexingService()
