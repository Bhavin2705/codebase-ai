import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.repository import Repository
from app.models.file import File as FileModel
from app.models.symbol import Symbol as SymbolModel
from app.services.embedding_service import EmbeddingService


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


class RetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    async def retrieve_contexts(
        self,
        question: str,
        repository_id: str,
        db: AsyncSession,
        top_k: int = 5
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        lowercase_question = question.strip().lower()

        # Retrieve repository details
        repo = None
        try:
            import uuid
            repo_uuid = uuid.UUID(repository_id)
            stmt_repo = select(Repository).where(Repository.id == repo_uuid)
            repo = (await db.execute(stmt_repo)).scalars().first()
        except ValueError:
            stmt_repo = select(Repository).where(Repository.name.ilike(f"%{repository_id}%"))
            repo = (await db.execute(stmt_repo)).scalars().first()

        if not repo:
            # Fallback to initial repository if not found
            stmt_repo = select(Repository)
            repo = (await db.execute(stmt_repo)).scalars().first()

        repo_meta = {
            "name": repo.name if repo else "Workspace",
            "language": repo.language if repo else "Multi-Language",
            "total_files": 0
        }

        if not repo:
            return [], repo_meta

        # Query files and symbols for the target repository
        stmt_files = select(FileModel).options(selectinload(FileModel.symbols)).where(FileModel.repository_id == repo.id)
        db_files = (await db.execute(stmt_files)).scalars().all()
        repo_meta["total_files"] = len(db_files)

        # Generate dense query embedding
        query_vector = []
        try:
            query_vector = await self.embedding_service.generate_embedding(question)
        except Exception as embed_err:
            print(f"Embedding error during context retrieval: {embed_err}")

        raw_tokens = set(re.findall(r"[A-Za-z0-9_]+", lowercase_question))
        stop_words = {"what", "how", "does", "the", "and", "for", "this", "repo", "repository", "workspace", "project", "where", "are", "code", "explain", "about", "is", "a", "an", "in", "of", "to"}
        query_terms = [t for t in raw_tokens if t not in stop_words and len(t) >= 2]

        is_overview_query = any(phrase in lowercase_question for phrase in [
            "what is this repo about", "repo about", "repository about", "overview", "what does this repo do",
            "architecture", "explain repo", "explain repository", "project structure", "readme",
            "workspace", "workspace about", "what is this workspace about", "project about", "explain project",
            "explain workspace", "what is this project about", "what does this project do", "summary", "about this"
        ])

        scored_contexts: List[Dict[str, Any]] = []

        for file_item in db_files:
            file_path = file_item.path
            content = file_item.content or ""
            file_path_lower = file_path.lower()
            content_lower = content.lower()
            symbols = file_item.symbols or []

            # 1. Lexical Scoring
            lexical_score = 0
            for term in query_terms:
                if term in file_path_lower.split("/")[-1]:
                    lexical_score += 40
                elif term in file_path_lower:
                    lexical_score += 15

                if any(term in sym.name.lower() for sym in symbols):
                    lexical_score += 25

                if term in content_lower:
                    lexical_score += min(content_lower.count(term), 5)

            # 2. Vector Similarity Scoring
            max_vector_score = 0.0
            best_symbol = None

            for sym in symbols:
                if sym.embedding and query_vector:
                    sim = cosine_similarity(query_vector, sym.embedding)
                    if sim > max_vector_score:
                        max_vector_score = sim
                        best_symbol = sym

            final_score = (max_vector_score * 100.0) + lexical_score

            if final_score > 0 or is_overview_query:
                lines = content.split("\n")
                start_line = best_symbol.start_line if best_symbol else 1
                end_line = best_symbol.end_line if best_symbol else min(len(lines), 150)
                sym_name = best_symbol.name if best_symbol else file_path.split("/")[-1]

                scored_contexts.append({
                    "score": final_score,
                    "context": {
                        "name": sym_name,
                        "file_path": file_path,
                        "signature": best_symbol.signature if best_symbol and best_symbol.signature else f"file {file_path}",
                        "start_line": start_line,
                        "end_line": end_line,
                        "source_code": best_symbol.source_code if (best_symbol and best_symbol.source_code) else content[:2500]
                    }
                })

        scored_contexts.sort(key=lambda item: item["score"], reverse=True)
        max_limit = top_k if not is_overview_query else 4
        contexts = [item["context"] for item in scored_contexts[:max_limit]]

        if not contexts and db_files:
            for file_item in db_files[:2]:
                content = file_item.content or ""
                lines = content.split("\n")
                contexts.append({
                    "name": file_item.path.split("/")[-1],
                    "file_path": file_item.path,
                    "signature": f"file {file_item.path}",
                    "start_line": 1,
                    "end_line": min(len(lines), 30),
                    "source_code": content[:300]
                })

        return contexts, repo_meta


retrieval_service = RetrievalService()
