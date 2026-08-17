import re
import uuid
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.repository import Repository
from app.models.file import File as FileModel
from app.models.symbol import Symbol as SymbolModel
from app.services.embedding_service import EmbeddingService

class RetrievalService:
    def __init__(self):
        self.embedder = EmbeddingService()

    async def retrieve_contexts(
        self,
        question: str,
        repository_id: str,
        db: AsyncSession,
        top_k: int = 5
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        query_text = question.strip().lower()

        repo = None
        try:
            repo_uuid = uuid.UUID(repository_id)
            stmt = select(Repository).where(Repository.id == repo_uuid)
            repo = (await db.execute(stmt)).scalars().first()
        except ValueError:
            stmt = select(Repository).where(Repository.name.ilike(f"%{repository_id}%"))
            repo = (await db.execute(stmt)).scalars().first()

        repo_meta = {
            "name": repo.name if repo else "Workspace",
            "language": repo.language if repo else "Multi-Language",
            "total_files": 0,
            "all_files": []
        }

        if not repo:
            return [], repo_meta

        # Single query: fetch all file paths for the active repository (sorted for determinism)
        stmt_paths = (
            select(FileModel.path)
            .where(FileModel.repository_id == repo.id)
            .order_by(FileModel.path)
        )
        all_file_paths: List[str] = list((await db.execute(stmt_paths)).scalars().all())
        repo_meta["all_files"] = all_file_paths
        repo_meta["total_files"] = len(all_file_paths)

        q_vec = []
        try:
            q_vec = await self.embedder.generate_embedding(question, input_type="query")
        except Exception:
            pass

        tokens = set(re.findall(r"[A-Za-z0-9_]+", query_text))
        stop = {
            "what", "how", "does", "the", "and", "for", "this", "repo", "repository",
            "workspace", "project", "where", "are", "code", "explain", "about", "is",
            "a", "an", "in", "of", "to", "me", "when", "asks", "keep", "your", "response",
            "precise", "tell", "show", "can", "you", "please"
        }
        query_terms = [t for t in tokens if t not in stop and len(t) >= 2]

        is_overview = any(p in query_text for p in [
            "what is this repo about", "repo about", "repository about", "overview", "what does this repo do",
            "architecture", "explain repo", "explain repository", "project structure", "readme",
            "workspace", "workspace about", "what is this workspace about", "project about", "explain project",
            "explain workspace", "what is this project about", "what does this project do", "summary", "about this",
            "flow of request", "request flow", "flow of the request", "how request works", "request processing"
        ])

        candidates: Dict[uuid.UUID, Dict[str, Any]] = {}

        # 1. Database-side pgvector similarity ranking
        if q_vec:
            try:
                cos_dist = SymbolModel.embedding.cosine_distance(q_vec)
                stmt_vector = (
                    select(SymbolModel, FileModel, cos_dist.label("dist"))
                    .join(FileModel, SymbolModel.file_id == FileModel.id)
                    .where(
                        FileModel.repository_id == repo.id,
                        SymbolModel.embedding.is_not(None)
                    )
                    .order_by(cos_dist)
                    .limit(top_k * 4)
                )
                vec_rows = (await db.execute(stmt_vector)).all()
                for sym, file_rec, dist in vec_rows:
                    vec_score = max(0.0, 1.0 - float(dist)) if dist is not None else 0.0
                    candidates[sym.id] = {
                        "sym": sym,
                        "file": file_rec,
                        "vec_score": vec_score
                    }
            except Exception:
                pass

        # 2. Database-side lexical matching for query terms
        if query_terms:
            lex_conditions = []
            for t in query_terms[:5]:
                pattern = f"%{t}%"
                lex_conditions.append(FileModel.path.ilike(pattern))
                lex_conditions.append(SymbolModel.name.ilike(pattern))

            stmt_lex = (
                select(SymbolModel, FileModel)
                .join(FileModel, SymbolModel.file_id == FileModel.id)
                .where(
                    FileModel.repository_id == repo.id,
                    or_(*lex_conditions)
                )
                .limit(top_k * 4)
            )
            lex_rows = (await db.execute(stmt_lex)).all()
            for sym, file_rec in lex_rows:
                if sym.id not in candidates:
                    candidates[sym.id] = {
                        "sym": sym,
                        "file": file_rec,
                        "vec_score": 0.0
                    }

        # 3. Fallback candidate loading if no candidates match yet
        if not candidates:
            stmt_fallback = (
                select(SymbolModel, FileModel)
                .join(FileModel, SymbolModel.file_id == FileModel.id)
                .where(FileModel.repository_id == repo.id)
                .limit(top_k * 2)
            )
            fallback_rows = (await db.execute(stmt_fallback)).all()
            for sym, file_rec in fallback_rows:
                candidates[sym.id] = {
                    "sym": sym,
                    "file": file_rec,
                    "vec_score": 0.0
                }

        # 4. Final hybrid scoring of candidates
        scored = []
        for cdata in candidates.values():
            sym = cdata["sym"]
            file_rec = cdata["file"]
            vec_score = cdata["vec_score"]

            file_path = file_rec.path
            path_lower = file_path.lower()
            sym_name_lower = sym.name.lower()

            lex_score = 0
            for term in query_terms:
                if term in path_lower.split("/")[-1]:
                    lex_score += 40
                elif term in path_lower:
                    lex_score += 15
                if term in sym_name_lower:
                    lex_score += 25

            # Heavily penalize dummy/test files so real source code is selected first
            if "dummy" in path_lower or "test_assets" in path_lower or "dummy_assets" in path_lower:
                lex_score -= 200

            total_score = (vec_score * 100.0) + lex_score
            lines = (file_rec.content or "").split("\n")
            start_l = sym.start_line or 1
            end_l = sym.end_line or min(len(lines), 150)

            scored.append({
                "score": total_score,
                "context": {
                    "name": sym.name,
                    "file_path": file_path,
                    "signature": sym.signature or f"file {file_path}",
                    "start_line": start_l,
                    "end_line": end_l,
                    "source_code": sym.source_code or (file_rec.content or "")[:2500]
                }
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        limit = top_k if not is_overview else 4
        contexts = [x["context"] for x in scored[:limit]]

        return contexts, repo_meta

retrieval_service = RetrievalService()
